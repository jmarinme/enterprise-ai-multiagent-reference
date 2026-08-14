"""Configurable, versioned model-pricing catalog and direct-model-cost calculator
(PBI-13-01 §15).

Prices are never hardcoded in Python or in the React frontend — they live in
configs/observability/pricing.json (path configurable via ObservabilitySettings), loaded once
and cached. Calculates DIRECT MODEL COST ONLY: input_tokens/1e6 * input_price +
output_tokens/1e6 * output_price. Never allocates shared Azure infrastructure cost (Container
Apps, Cosmos DB, Application Insights, networking, AI Search) — see PBI-13-01 §15.

Unknown pricing (no catalog entry for a model, or an empty catalog) returns
(None, catalog_version) — "Unavailable", never a fabricated zero.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path


@dataclass(frozen=True)
class PriceEntry:
    model: str
    effective_date: date
    input_price_per_million_tokens_usd: float
    output_price_per_million_tokens_usd: float


class PricingCatalog:
    """Loads and queries the versioned model-price catalog. Read-only after construction —
    reload() exists only for tests/local iteration, never called on the request path."""

    def __init__(self, catalog_path: Path) -> None:
        self._catalog_path = catalog_path
        self._version = "unknown"
        self._entries: dict[str, list[PriceEntry]] = {}
        self.reload()

    def reload(self) -> None:
        if not self._catalog_path.exists():
            self._version = "missing"
            self._entries = {}
            return
        raw = json.loads(self._catalog_path.read_text(encoding="utf-8"))
        self._version = raw.get("catalogVersion", "unknown")
        entries: dict[str, list[PriceEntry]] = {}
        for item in raw.get("entries", []):
            entry = PriceEntry(
                model=item["model"],
                effective_date=date.fromisoformat(item["effectiveDate"]),
                input_price_per_million_tokens_usd=float(item["inputPricePerMillionTokensUsd"]),
                output_price_per_million_tokens_usd=float(item["outputPricePerMillionTokensUsd"]),
            )
            entries.setdefault(entry.model, []).append(entry)
        for model_entries in entries.values():
            model_entries.sort(key=lambda e: e.effective_date, reverse=True)
        self._entries = entries

    @property
    def version(self) -> str:
        return self._version

    def find_price(self, model: str | None, as_of: date | None = None) -> PriceEntry | None:
        """Returns the latest price entry for `model` effective on or before `as_of`
        (defaults to today), or None if the model has no catalog entry at all — the caller
        must treat that as Unavailable, never a zero-cost run."""
        if model is None:
            return None
        candidates = self._entries.get(model)
        if not candidates:
            return None
        cutoff = as_of or datetime.now(tz=UTC).date()
        for entry in candidates:
            if entry.effective_date <= cutoff:
                return entry
        return None

    def estimate_cost_usd(
        self, model: str | None, input_tokens: int | None, output_tokens: int | None
    ) -> tuple[float | None, str]:
        """Returns (estimated_cost_usd_or_None, catalog_version_used). None means
        Unavailable — either the model isn't priced, or token counts are unavailable."""
        if input_tokens is None or output_tokens is None:
            return None, self._version
        price = self.find_price(model)
        if price is None:
            return None, self._version
        cost = (
            input_tokens / 1_000_000 * price.input_price_per_million_tokens_usd
            + output_tokens / 1_000_000 * price.output_price_per_million_tokens_usd
        )
        return cost, self._version

"""Unit tests for src.observability.pricing.PricingCatalog (PBI-13-01 §15).

Covers: direct-model-cost formula, unknown pricing -> Unavailable (never zero), price
versioning/effective-date selection, and that the loaded catalog version is always returned
alongside a cost (for persisting the pricing snapshot used).
"""

import json
from pathlib import Path

import pytest

from src.observability.pricing import PricingCatalog


@pytest.fixture
def catalog_path(tmp_path: Path) -> Path:
    path = tmp_path / "pricing.json"
    path.write_text(
        json.dumps(
            {
                "catalogVersion": "2026-01-01.1",
                "entries": [
                    {
                        "model": "gpt-5-mini",
                        "effectiveDate": "2026-01-01",
                        "inputPricePerMillionTokensUsd": 1.0,
                        "outputPricePerMillionTokensUsd": 4.0,
                    },
                    {
                        "model": "gpt-5-mini",
                        "effectiveDate": "2026-06-01",
                        "inputPricePerMillionTokensUsd": 0.5,
                        "outputPricePerMillionTokensUsd": 2.0,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_estimate_cost_usd_applies_the_direct_model_cost_formula(catalog_path: Path) -> None:
    catalog = PricingCatalog(catalog_path)

    from datetime import date

    price = catalog.find_price("gpt-5-mini", as_of=date(2026, 1, 15))
    assert price is not None
    cost, version = catalog.estimate_cost_usd("gpt-5-mini", 1_000_000, 500_000)

    # As-of "today" resolves to the latest effective entry (0.5/2.0), not the 2026-01-01 one.
    assert cost == pytest.approx(1_000_000 / 1_000_000 * 0.5 + 500_000 / 1_000_000 * 2.0)
    assert version == "2026-01-01.1"


def test_estimate_cost_usd_selects_the_latest_entry_effective_on_or_before_the_date(
    catalog_path: Path,
) -> None:
    from datetime import date

    catalog = PricingCatalog(catalog_path)

    early_price = catalog.find_price("gpt-5-mini", as_of=date(2026, 3, 1))
    assert early_price is not None
    assert early_price.input_price_per_million_tokens_usd == 1.0

    late_price = catalog.find_price("gpt-5-mini", as_of=date(2026, 7, 1))
    assert late_price is not None
    assert late_price.input_price_per_million_tokens_usd == 0.5


def test_estimate_cost_usd_is_unavailable_for_an_unpriced_model(catalog_path: Path) -> None:
    catalog = PricingCatalog(catalog_path)

    cost, version = catalog.estimate_cost_usd("some-other-model", 100, 100)

    assert cost is None
    assert version == "2026-01-01.1"


def test_estimate_cost_usd_is_unavailable_when_tokens_are_unavailable(catalog_path: Path) -> None:
    catalog = PricingCatalog(catalog_path)

    cost, _version = catalog.estimate_cost_usd("gpt-5-mini", None, None)

    assert cost is None


def test_empty_catalog_never_fabricates_a_cost(tmp_path: Path) -> None:
    path = tmp_path / "empty.json"
    path.write_text(json.dumps({"catalogVersion": "empty", "entries": []}), encoding="utf-8")
    catalog = PricingCatalog(path)

    cost, version = catalog.estimate_cost_usd("gpt-5-mini", 1000, 1000)

    assert cost is None
    assert version == "empty"


def test_missing_catalog_file_never_raises_and_reports_missing(tmp_path: Path) -> None:
    catalog = PricingCatalog(tmp_path / "does-not-exist.json")

    cost, version = catalog.estimate_cost_usd("gpt-5-mini", 1000, 1000)

    assert cost is None
    assert version == "missing"

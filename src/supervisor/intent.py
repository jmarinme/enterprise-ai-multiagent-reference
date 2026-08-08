"""Rule-based intent resolution.

No LLM, no embeddings, no AI of any kind — this resolver exists only to validate the
orchestration architecture end-to-end. A future PBI may add an LLM-backed resolver behind
the same IntentResolver Protocol without changing the Supervisor.

PBI-04-04: keyword lists are bilingual (English + es-MX) so the same rule-based resolver
routes correctly regardless of which language the caller is using — the platform's default
audience (Tokio Marine Mexico) types in Spanish. Order (CLAIMS -> BROKER -> COMMERCIAL) and
first-match-wins semantics are unchanged from the English-only version.
"""

from __future__ import annotations

from typing import Protocol

from src.supervisor.models import Intent, IntentCategory

_CLAIMS_KEYWORDS = (
    "claim", "accident", "siniestro", "adjuster", "damage",
    "accidente", "choque", "reportar un accidente", "reportar un siniestro", "tuve un choque",
)
_BROKER_KEYWORDS = (
    "broker", "commission", "policy", "transaction", "receipt", "payment",
    "comisión", "comision", "comisiones", "pago de comisión", "pago de comision",
    "corredor", "correduría", "correduria", "recibo",
)
_COMMERCIAL_KEYWORDS = (
    "quote", "new business", "commercial", "lead", "coverage options",
    "cotización", "cotizacion", "asegurar mi empresa", "asegurar", "empresa",
    "seguro comercial", "negocio",
)


class IntentResolver(Protocol):
    """Contract for resolving a synthetic intent from a raw message."""

    async def resolve(self, message: str) -> Intent: ...


class RuleBasedIntentResolver:
    """Deterministic keyword-matching resolver. No AI involved."""

    async def resolve(self, message: str) -> Intent:
        normalized = message.lower()

        if any(keyword in normalized for keyword in _CLAIMS_KEYWORDS):
            return Intent(category=IntentCategory.CLAIMS, confidence=1.0)

        if any(keyword in normalized for keyword in _BROKER_KEYWORDS):
            return Intent(category=IntentCategory.BROKER, confidence=1.0)

        if any(keyword in normalized for keyword in _COMMERCIAL_KEYWORDS):
            return Intent(category=IntentCategory.COMMERCIAL, confidence=1.0)

        return Intent(category=IntentCategory.UNKNOWN, confidence=0.0)

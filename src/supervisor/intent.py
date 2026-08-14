"""Rule-based intent resolution.

No LLM, no embeddings, no AI of any kind — this resolver exists only to validate the
orchestration architecture end-to-end. A future PBI may add an LLM-backed resolver behind
the same IntentResolver Protocol without changing the Supervisor.

PBI-04-04: keyword lists are bilingual (English + es-MX) so the same rule-based resolver
routes correctly regardless of which language the caller is using — the platform's default
audience (Tokio Marine Mexico) types in Spanish. Order (CLAIMS -> BROKER -> COMMERCIAL) and
first-match-wins semantics are unchanged from the English-only version.

PBI-05-01: a caller describing a Property loss ("Se inundó mi casa.") often never says
"siniestro"/"accidente" at all — found via live DEV validation, where this exact PBI-provided
example fell through to FallbackAgent. _CLAIMS_KEYWORDS gained loss-type-describing words
(flood/fire/theft/hail/collision-describing verbs) covering both Auto and Property claims, not
just the generic "I have a claim" phrasing.

PBI-14-03 section 5: a caller requesting NEW commercial coverage against a peril ("quiero
asegurar una fábrica en Monterrey por 20 millones contra incendio") mentions a loss-type word
("incendio") that is also a _CLAIMS_KEYWORDS entry — bare first-match-wins order would
misroute this to Claims. _is_new_commercial_insurance_request below is a genuinely deterministic
(zero-LLM) compound-pattern rule checked before _CLAIMS_KEYWORDS specifically to resolve this
collision, still entirely within RuleBasedIntentResolver — the Supervisor remains deterministic
end to end (ADR-0011). Also added the accented "póliza"/"poliza" and a bare "pago" to
_BROKER_KEYWORDS: PBI-14-01's gap analysis found a Spanish-only policy/payment-status inquiry
with neither an English keyword nor a compound "pago de comisión" phrase had no matching
keyword at all and fell through to FallbackAgent.
"""

from __future__ import annotations

from typing import Protocol

from src.supervisor.models import Intent, IntentCategory

_CLAIMS_KEYWORDS = (
    "claim", "accident", "siniestro", "adjuster", "damage",
    "accidente", "choque", "reportar un accidente", "reportar un siniestro", "tuve un choque",
    # Loss-type-describing words (PBI-05-01): a caller describing what happened often never
    # says "siniestro"/"accidente" explicitly, especially for Property losses.
    "inund", "incendio", "robaron", "me robaron", "granizo", "granizada", "vandalismo",
    "se dañó", "se dañaron", "chocaron", "me chocaron", "flood", "fire", "hail", "stolen",
    "vandalism", "collision",
)
_BROKER_KEYWORDS = (
    "broker", "commission", "policy", "transaction", "receipt", "payment",
    "comisión", "comision", "comisiones", "pago de comisión", "pago de comision",
    "corredor", "correduría", "correduria", "recibo",
    # PBI-14-03 gap fix (see module docstring): the accented Spanish term for "policy" and a
    # bare (non-compound) "pago" were both entirely absent before this PBI.
    "póliza", "poliza", "pago",
)
_COMMERCIAL_KEYWORDS = (
    "quote", "new business", "commercial", "lead", "coverage options",
    "cotización", "cotizacion", "asegurar mi empresa", "asegurar", "empresa",
    "seguro comercial", "negocio",
)

# PBI-14-03 section 5: a NEW-commercial-insurance-request pattern — an "asegurar" family verb
# together with a business-premises/entity noun — deterministically outranks a bare
# _CLAIMS_KEYWORDS loss-type-word collision (e.g. "incendio"/"fire", also a peril being
# insured against, not a loss being reported). Intentionally narrow (verb AND noun, not either
# alone): "asegurar" alone is already a weaker _COMMERCIAL_KEYWORDS fallback entry, and a noun
# alone (e.g. "empresa") must not override a genuine claims report ("tuve un accidente con el
# coche de la empresa").
_COMMERCIAL_INSURANCE_VERBS = ("asegurar", "insure", "cover", "coverage for")
_COMMERCIAL_BUSINESS_NOUNS = (
    "fábrica", "fabrica", "empresa", "negocio", "compañía", "compania", "company", "business",
    "planta", "bodega", "sucursal", "oficina",
)


def _is_new_commercial_insurance_request(normalized: str) -> bool:
    has_verb = any(verb in normalized for verb in _COMMERCIAL_INSURANCE_VERBS)
    has_noun = any(noun in normalized for noun in _COMMERCIAL_BUSINESS_NOUNS)
    return has_verb and has_noun


class IntentResolver(Protocol):
    """Contract for resolving a synthetic intent from a raw message."""

    async def resolve(self, message: str) -> Intent: ...


class RuleBasedIntentResolver:
    """Deterministic keyword-matching resolver. No AI involved."""

    async def resolve(self, message: str) -> Intent:
        normalized = message.lower()

        if _is_new_commercial_insurance_request(normalized):
            return Intent(category=IntentCategory.COMMERCIAL, confidence=1.0)

        if any(keyword in normalized for keyword in _CLAIMS_KEYWORDS):
            return Intent(category=IntentCategory.CLAIMS, confidence=1.0)

        if any(keyword in normalized for keyword in _BROKER_KEYWORDS):
            return Intent(category=IntentCategory.BROKER, confidence=1.0)

        if any(keyword in normalized for keyword in _COMMERCIAL_KEYWORDS):
            return Intent(category=IntentCategory.COMMERCIAL, confidence=1.0)

        return Intent(category=IntentCategory.UNKNOWN, confidence=0.0)

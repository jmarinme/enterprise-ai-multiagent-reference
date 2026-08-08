"""Shared Conversational Policy (PBI-05-01) — controls HOW Claims/Broker/Commercial/Fallback
communicate, never WHAT business facts they report. Every business fact still comes from a
Tool result (CLAUDE.md §3); this module only supplies the acknowledgment/empathy phrasing that
wraps around those facts, so the platform reads like an insurance advisor instead of a
questionnaire.

Deliberately small and template-based, not LLM-generated: response text must stay deterministic
and testable (CLAUDE.md architecture principle #2, unchanged since PBI-04-04's own bilingual
message catalogs) — this module is a shared *vocabulary* other agents' catalogs draw from, not
a new response-authoring mechanism.
"""

from __future__ import annotations

from src.agents.shared.language import Language

# Natural-language labels for the canonical loss_type values both Claims profiles (Auto and
# Property — see src.agents.claims.state) can produce, so the acknowledgment reads naturally
# regardless of which one is in play ("una inundación", not "water damage").
_LOSS_TYPE_LABELS: dict[str, dict[Language, str]] = {
    "collision": {"es-MX": "una colisión", "en": "a collision"},
    "theft": {"es-MX": "un robo", "en": "a theft"},
    "glass": {"es-MX": "un daño en cristales", "en": "glass damage"},
    "vandalism": {"es-MX": "vandalismo", "en": "vandalism"},
    "weather": {"es-MX": "un evento climático", "en": "a weather event"},
    "fire": {"es-MX": "un incendio", "en": "a fire"},
    "water damage": {"es-MX": "una inundación", "en": "water damage"},
    "other": {"es-MX": "el incidente que reportas", "en": "the incident you're reporting"},
}

_EMPATHY_OPENER: dict[Language, str] = {
    "es-MX": "Lamento lo ocurrido.",
    "en": "I'm sorry to hear that.",
}

_HELP_TRANSITION: dict[Language, str] = {
    "es-MX": "Voy a ayudarte a registrar el aviso.",
    "en": "I'll help you register the notice.",
}

_BARE_ACKNOWLEDGMENT: dict[Language, str] = {
    "es-MX": "Claro.",
    "en": "Of course.",
}


def loss_type_label(loss_type: str | None, language: Language) -> str:
    """A natural noun phrase for a canonical loss_type value ("water damage" -> "una
    inundación"), falling back to a generic phrase for an unrecognized or absent value —
    never a raw internal token shown to the user."""
    entry = _LOSS_TYPE_LABELS.get(loss_type or "", _LOSS_TYPE_LABELS["other"])
    return entry.get(language) or entry["es-MX"]


def opening_acknowledgment(*, loss_type: str | None, language: Language) -> str:
    """The conversation's opening acknowledgment, said exactly once per conversation
    (src.agents.claims.state.ClaimsIntakeState.opening_acknowledged tracks this) before the
    first real question. Two shapes:
    - loss_type already known from the caller's own opening message: empathy + transition +
      an explicit "ya entendí que se trata de X" acknowledgment (the PBI's own preferred
      example, generalized to any loss type).
    - loss_type not yet known (a bare "quiero reportar un siniestro"): a short, warm "Claro."
      lead-in instead of manufacturing empathy for a fact that hasn't been shared yet."""
    if loss_type is None:
        return _BARE_ACKNOWLEDGMENT.get(language) or _BARE_ACKNOWLEDGMENT["es-MX"]

    empathy = _EMPATHY_OPENER.get(language) or _EMPATHY_OPENER["es-MX"]
    transition = _HELP_TRANSITION.get(language) or _HELP_TRANSITION["es-MX"]
    label = loss_type_label(loss_type, language)
    if language == "en":
        return f"{empathy} {transition} I understand this involves {label}."
    return f"{empathy} {transition} Ya entendí que se trata de {label}."

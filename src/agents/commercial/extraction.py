"""Deterministic field extraction for commercial intake (PBI-01-07, bilingual keyword coverage
added by PBI-04-04, natural name-prefix stripping added by PBI-05-01).

MockLLMProvider is intentionally content-agnostic and cannot perform real NLU, so every
business fact must come from regex/keyword rules here — same rationale as
src.agents.claims.extraction and src.agents.broker.extraction.
"""

from __future__ import annotations

import re

from src.agents.commercial.state import CommercialIntakeState
from src.agents.shared.nlu import strip_natural_prefix

_EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
# 3-3-4 digit grouping (optionally with a country code), same shape as
# src.agents.claims.extraction's phone pattern.
_PHONE_PATTERN = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")

_CHANNEL_KEYWORDS: dict[str, str] = {
    "e-mail": "email",
    "email": "email",
    "correo": "email",
    "correo electrónico": "email",
    "correo electronico": "email",
    "phone": "phone",
    "call": "phone",
    "telephone": "phone",
    "teléfono": "phone",
    "telefono": "phone",
    "llamada": "phone",
}

_INSURANCE_NEED_KEYWORDS: dict[str, str] = {
    "general liability": "general liability",
    "liability": "general liability",
    "responsabilidad civil": "general liability",
    "property": "commercial property",
    "propiedad": "commercial property",
    "commercial auto": "commercial auto",
    "auto": "commercial auto",
    "workers compensation": "workers compensation",
    "workers comp": "workers compensation",
    "riesgos de trabajo": "workers compensation",
    "cyber": "cyber liability",
    "cibernético": "cyber liability",
    "cibernetico": "cyber liability",
    "professional liability": "professional liability",
    "errors and omissions": "professional liability",
    "responsabilidad profesional": "professional liability",
}

# Fields free-form enough that, absent any structured match, the raw answer to the most
# recently asked question is attributed to them. contact_email/contact_phone/
# preferred_contact_channel have their own regex/keyword extraction and never fall back this
# way, so an unrecognized answer to one of those correctly leaves the field missing and
# re-prompts, rather than silently accepting bad data.
_FREE_TEXT_FALLBACK_FIELDS = {"company_name", "contact_name", "risk_description", "insurance_need"}

# "mi empresa es Acme Corp" -> "Acme Corp"; "mi nombre es Jane Doe" -> "Jane Doe" (PBI-05-01
# requirement 3, generalized from Claims' customer_name/Broker's broker_name handling).
_COMPANY_NAME_PREFIXES: tuple[str, ...] = ("mi empresa es", "nuestra empresa es", "somos")
_CONTACT_NAME_PREFIXES: tuple[str, ...] = ("mi nombre es", "me llamo", "soy")


def extract_fields(message: str, state: CommercialIntakeState) -> CommercialIntakeState:
    """Return a copy of state with any recognizable fields from message filled in."""
    updated = state.model_copy()
    normalized = message.strip()
    lowered = normalized.lower()
    matched_structured_field = False

    if updated.contact_email is None:
        email_match = _EMAIL_PATTERN.search(normalized)
        if email_match:
            updated.contact_email = email_match.group(0)
            matched_structured_field = True

    if updated.contact_phone is None:
        phone_match = _PHONE_PATTERN.search(normalized)
        if phone_match:
            updated.contact_phone = phone_match.group(0).strip()
            matched_structured_field = True

    if updated.preferred_contact_channel is None:
        for keyword, canonical in _CHANNEL_KEYWORDS.items():
            if keyword in lowered:
                updated.preferred_contact_channel = canonical
                matched_structured_field = True
                break

    if updated.insurance_need is None:
        for keyword, canonical in _INSURANCE_NEED_KEYWORDS.items():
            if keyword in lowered:
                updated.insurance_need = canonical
                matched_structured_field = True
                break

    if (
        not matched_structured_field
        and state.last_asked_field in _FREE_TEXT_FALLBACK_FIELDS
        and getattr(updated, state.last_asked_field) is None
        and normalized
    ):
        value = normalized
        if state.last_asked_field == "company_name":
            value = strip_natural_prefix(normalized, _COMPANY_NAME_PREFIXES)
        elif state.last_asked_field == "contact_name":
            value = strip_natural_prefix(normalized, _CONTACT_NAME_PREFIXES)
        setattr(updated, state.last_asked_field, value)

    return updated

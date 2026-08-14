"""Typed working state for a single conversation's commercial-intake flow (PBI-01-07, bilingual
messages added by PBI-04-04).

Structurally mirrors src.agents.claims.state (single linear flow — unlike Broker, there is no
"inquiry type" dimension here, every conversation collects the same lead fields). This is
in-progress session notes, not core business truth (CLAUDE.md §4.3), serialized into
Conversation.metadata["commercialIntakeState"]. The authoritative record is whatever
LeadRegistrationTool simulates on the caller's behalf.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from src.agents.shared.language import Language


class CommercialIntakeStatus(str, Enum):
    """The commercial-intake state machine. CONFIRMING (PBI-14-03) sits between
    COLLECTING_INFORMATION and READY_TO_REGISTER: a lead is no longer registered automatically
    the instant the last required field is filled — the caller must explicitly confirm first
    (CLAUDE.md §5, Human-in-the-Loop; PBI-14-03 section 11)."""

    NEW = "new"
    COLLECTING_INFORMATION = "collecting_information"
    CONFIRMING = "confirming"
    READY_TO_REGISTER = "ready_to_register"
    REGISTERED = "registered"


class CommercialIntakeState(BaseModel):
    """Everything the Agent needs to resume a commercial-intake conversation on the next turn."""

    status: CommercialIntakeStatus = CommercialIntakeStatus.NEW

    company_name: str | None = None
    contact_name: str | None = None
    preferred_contact_channel: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    insurance_need: str | None = None
    risk_description: str | None = None

    # Qualification/intake context only (PBI-14-03 section 6) — never sent to
    # LeadRegistrationTool, never used to price, quote, underwrite, or approve risk/coverage
    # (CLAUDE.md §2). Populated only by the shared semantic-interpretation layer (there is no
    # deterministic regex/keyword extractor for these), shown back to the caller in the
    # pre-registration confirmation summary so they can correct a mis-heard value.
    industry: str | None = None
    location: str | None = None
    insured_value: str | None = None

    # Explicit pre-registration confirmation (PBI-14-03 section 11) — None until asked,
    # True/False once the caller answers. Mirrors src.agents.claims.state.ClaimsIntakeState's
    # own `confirmed` field.
    confirmed: bool | None = None

    lead_reference: str | None = None

    # Tracks which field the last question was about, so a free-text answer with no
    # recognizable structure (e.g. a risk description) can be attributed correctly.
    last_asked_field: str | None = None


FIELD_PROMPTS: dict[str, dict[Language, str]] = {
    "company_name": {
        "es-MX": "¿Cuál es el nombre de tu empresa o negocio?",
        "en": "What is your company or business name?",
    },
    "contact_name": {
        "es-MX": "¿Cuál es el nombre completo de la persona de contacto?",
        "en": "What is the best contact person's full name?",
    },
    "preferred_contact_channel": {
        "es-MX": "¿Prefieres que te contactemos por correo electrónico o por teléfono?",
        "en": "Would you prefer to be contacted by email or phone?",
    },
    "contact_email": {
        "es-MX": "¿Cuál es el mejor correo electrónico para contactarte?",
        "en": "What is the best email address to reach you?",
    },
    "contact_phone": {
        "es-MX": "¿Cuál es el mejor teléfono para contactarte?",
        "en": "What is the best phone number to reach you?",
    },
    "insurance_need": {
        "es-MX": "¿Qué tipo de seguro o cobertura estás buscando?",
        "en": "What type of insurance or coverage are you looking for?",
    },
    "risk_description": {
        "es-MX": "¿Podrías describir brevemente tu negocio o el riesgo que te gustaría cubrir?",
        "en": "Could you briefly describe your business or the risk you'd like covered?",
    },
}


def missing_required_fields(state: CommercialIntakeState) -> list[str]:
    """The single next-missing required field, in the order it should be asked (one at a time,
    mirroring src.agents.claims.state's pattern) — empty once every required field, including
    whichever contact detail matches preferred_contact_channel, is filled."""
    if state.company_name is None:
        return ["company_name"]
    if state.contact_name is None:
        return ["contact_name"]
    if state.preferred_contact_channel is None:
        return ["preferred_contact_channel"]
    if state.preferred_contact_channel == "email" and state.contact_email is None:
        return ["contact_email"]
    if state.preferred_contact_channel == "phone" and state.contact_phone is None:
        return ["contact_phone"]
    if state.insurance_need is None:
        return ["insurance_need"]
    if state.risk_description is None:
        return ["risk_description"]
    return []

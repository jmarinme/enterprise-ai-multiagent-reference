"""Typed working state for a single conversation's commercial-intake flow (PBI-01-07).

Structurally mirrors src.agents.claims.state (single linear flow — unlike Broker, there is no
"inquiry type" dimension here, every conversation collects the same lead fields). This is
in-progress session notes, not core business truth (CLAUDE.md §4.3), serialized into
Conversation.metadata["commercialIntakeState"]. The authoritative record is whatever
LeadRegistrationTool simulates on the caller's behalf.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class CommercialIntakeStatus(str, Enum):
    """The commercial-intake state machine."""

    NEW = "new"
    COLLECTING_INFORMATION = "collecting_information"
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

    lead_reference: str | None = None

    # Tracks which field the last question was about, so a free-text answer with no
    # recognizable structure (e.g. a risk description) can be attributed correctly.
    last_asked_field: str | None = None


FIELD_PROMPTS: dict[str, str] = {
    "company_name": "What is your company or business name?",
    "contact_name": "What is the best contact person's full name?",
    "preferred_contact_channel": "Would you prefer to be contacted by email or phone?",
    "contact_email": "What is the best email address to reach you?",
    "contact_phone": "What is the best phone number to reach you?",
    "insurance_need": "What type of insurance or coverage are you looking for?",
    "risk_description": "Could you briefly describe your business or the risk you'd like covered?",
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

"""Typed working state for a single conversation's claims-intake flow (PBI-01-05).

This is deliberately NOT core business truth (CLAUDE.md §4.3 forbids storing authoritative
policy/claim/payment data in the Conversation store) — it is in-progress session notes the
Agent needs to resume a multi-turn intake across turns, serialized into
Conversation.metadata["claimsIntakeState"]. The authoritative record is whatever
ClaimRegistrationTool simulates on the caller's behalf.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class ClaimsIntakeStatus(str, Enum):
    """The claims-intake state machine (suggested by PBI-01-05)."""

    NEW = "new"
    COLLECTING_INFORMATION = "collecting_information"
    VALIDATING_POLICY = "validating_policy"
    READY_TO_REGISTER = "ready_to_register"
    REGISTERED = "registered"
    ADJUSTER_ASSIGNED = "adjuster_assigned"


class ClaimsIntakeState(BaseModel):
    """Everything the Agent needs to resume a claims-intake conversation on the next turn."""

    status: ClaimsIntakeStatus = ClaimsIntakeStatus.NEW

    policy_number: str | None = None
    event_date: str | None = None
    event_time: str | None = None
    event_location: str | None = None
    loss_type: str | None = None
    loss_description: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    injuries_reported: bool | None = None
    third_parties_involved: bool | None = None

    policy_validated: bool = False
    policy_active: bool | None = None
    payment_current: bool | None = None

    claim_reference: str | None = None
    adjuster_assigned: str | None = None

    # Tracks which field the last question was about, so a free-text answer with no
    # recognizable structure (e.g. a loss description) can be attributed correctly.
    last_asked_field: str | None = None


# Order matters: this is also the order fields are asked for, one at a time.
REQUIRED_FIELDS: tuple[str, ...] = (
    "policy_number",
    "event_date",
    "event_location",
    "loss_type",
    "loss_description",
    "contact_name",
    "contact_phone",
    "injuries_reported",
    "third_parties_involved",
)

# Fields the state machine will opportunistically capture when volunteered, but never asks for.
OPTIONAL_FIELDS: tuple[str, ...] = ("event_time", "contact_email")

FIELD_PROMPTS: dict[str, str] = {
    "policy_number": "Could you provide your policy number?",
    "event_date": "What date did the incident occur? (YYYY-MM-DD)",
    "event_location": "Where did the incident take place?",
    "loss_type": (
        "What type of loss is this (e.g., collision, theft, fire, water damage, weather, "
        "vandalism, other)?"
    ),
    "loss_description": "Could you briefly describe what happened?",
    "contact_name": "What is your full name for this claim?",
    "contact_phone": "What is the best phone number to reach you?",
    "injuries_reported": "Were there any injuries involved? (yes/no)",
    "third_parties_involved": "Were any third parties involved? (yes/no)",
}


def missing_required_fields(state: ClaimsIntakeState) -> list[str]:
    """Required fields still unanswered, in the order they should be asked."""
    return [field for field in REQUIRED_FIELDS if getattr(state, field) is None]

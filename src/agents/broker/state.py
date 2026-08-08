"""Typed working state for a single conversation's broker-services flow (PBI-01-06, bilingual
messages added by PBI-04-04).

Structurally mirrors src.agents.claims.state (same reasoning: this is in-progress session
notes, not core business truth — CLAUDE.md §4.3 — serialized into
Conversation.metadata["brokerInquiryState"]). Not extracted into a shared base with the Claims
state model: only two data points exist so far, and the PBI explicitly warns against
over-generalizing after seeing only two agents — see docs/sprint_01/decisions.md.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from src.agents.shared.language import Language
from src.agents.shared.messages import t


class BrokerInquiryType(str, Enum):
    """Which kind of broker-services request this conversation is handling."""

    POLICY_STATUS = "policy_status"
    TRANSACTION_STATUS = "transaction_status"
    COMMISSION = "commission"


class BrokerInquiryStatus(str, Enum):
    """The broker-services state machine (suggested by PBI-01-06, with the commission-payment
    sub-flow folded into the same single state machine rather than a parallel one — see
    docs/sprint_01/decisions.md)."""

    NEW = "new"
    IDENTIFYING_REQUEST = "identifying_request"
    COLLECTING_INFORMATION = "collecting_information"
    LOOKING_UP_DATA = "looking_up_data"
    READY_TO_RESPOND = "ready_to_respond"
    READY_TO_REQUEST_PAYMENT = "ready_to_request_payment"
    PAYMENT_REQUEST_REGISTERED = "payment_request_registered"
    COMPLETED = "completed"


class BrokerInquiryState(BaseModel):
    """Everything the Agent needs to resume a broker-services conversation on the next turn."""

    status: BrokerInquiryStatus = BrokerInquiryStatus.NEW
    inquiry_type: BrokerInquiryType | None = None

    broker_id: str | None = None
    policy_number: str | None = None
    transaction_reference: str | None = None
    commission_period: str | None = None

    broker_active: bool | None = None
    policy_status: str | None = None
    policy_payment_current: bool | None = None
    transaction_status: str | None = None
    commission_amount: float | None = None
    commission_status: str | None = None
    payment_request_reference: str | None = None

    wants_payment_request: bool | None = None
    next_required_fields: list[str] = Field(default_factory=list)

    # Tracks which field the last question was about, so a plain "yes"/"no" answer with no
    # recognizable structure can be attributed correctly.
    last_asked_field: str | None = None


REQUIRED_FIELDS_BY_INQUIRY: dict[BrokerInquiryType, tuple[str, ...]] = {
    BrokerInquiryType.POLICY_STATUS: ("policy_number",),
    BrokerInquiryType.TRANSACTION_STATUS: ("transaction_reference",),
    BrokerInquiryType.COMMISSION: ("broker_id", "commission_period"),
}

FIELD_PROMPTS: dict[str, dict[Language, str]] = {
    "policy_number": {
        "es-MX": "Por favor indica el número de póliza sintética.",
        "en": "Please provide the synthetic policy number.",
    },
    "transaction_reference": {
        "es-MX": "Por favor indica la referencia de transacción sintética.",
        "en": "Please provide the synthetic transaction reference.",
    },
    "broker_id": {
        "es-MX": "Por favor indica tu ID de corredor sintético.",
        "en": "Please provide your synthetic broker ID.",
    },
    "commission_period": {
        "es-MX": "¿Qué período de comisión te gustaría revisar (por ejemplo, 2026-Q1)?",
        "en": "Which commission period would you like to review (e.g., 2026-Q1)?",
    },
}

# Matches the PBI's own example dialogue verbatim when both commission fields are missing at
# once, rather than asking for them one at a time as ClaimsAgent does — this Agent's examples
# explicitly show both fields requested together.
_COMBINED_COMMISSION_PROMPT: dict[Language, str] = {
    "es-MX": "Por favor indica tu ID de corredor y el período que deseas revisar.",
    "en": "Please provide your broker ID and the period you want to review.",
}


def missing_required_fields(state: BrokerInquiryState) -> list[str]:
    """Required fields still unanswered for the current inquiry_type, in prompt order."""
    if state.inquiry_type is None:
        return []
    required = REQUIRED_FIELDS_BY_INQUIRY[state.inquiry_type]
    return [field for field in required if getattr(state, field) is None]


def prompt_for_missing(missing: list[str], language: Language) -> str:
    """One combined, professional prompt for every currently-missing field."""
    if set(missing) == {"broker_id", "commission_period"}:
        return _COMBINED_COMMISSION_PROMPT.get(language) or _COMBINED_COMMISSION_PROMPT["es-MX"]
    return " ".join(t(FIELD_PROMPTS, field, language) for field in missing)

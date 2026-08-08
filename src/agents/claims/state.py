"""Typed working state for a single conversation's claims-intake flow (PBI-01-05, extended by
PBI-04-04 with customer discovery, coverage validation, and an explicit confirmation step).

This is deliberately NOT core business truth (CLAUDE.md §4.3 forbids storing authoritative
policy/claim/payment data in the Conversation store) — it is in-progress session notes the
Agent needs to resume a multi-turn intake across turns, serialized into
Conversation.metadata["claimsIntakeState"]. The authoritative record is whatever
ClaimRegistrationTool simulates on the caller's behalf.

PBI-04-04 changes the very first question from "what is your policy number?" to "what is your
name?" (CUSTOMER DISCOVERY requirement): a caller who already knows their policy number can
still just type it — the regex-based extractor in src.agents.claims.extraction always recognizes
one wherever it appears, which skips customer lookup entirely (see workflow._handle_collecting_
information). Everything customer discovery needs to disambiguate ("la primera", "la segunda",
"la Hilux", "la de auto") lives in `candidates`.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from src.agents.shared.language import Language


class ClaimsIntakeStatus(str, Enum):
    """The claims-intake state machine (PBI-01-05, extended by PBI-04-04)."""

    NEW = "new"
    COLLECTING_INFORMATION = "collecting_information"
    LOOKING_UP_CUSTOMER = "looking_up_customer"
    SELECTING_POLICY = "selecting_policy"
    VALIDATING_POLICY = "validating_policy"
    CONFIRMING = "confirming"
    READY_TO_REGISTER = "ready_to_register"
    REGISTERED = "registered"
    ADJUSTER_ASSIGNED = "adjuster_assigned"


class PolicyCandidate(BaseModel):
    """One selectable policy surfaced by a customer_lookup match — enough to both display it
    ("la Hilux", "tu póliza de auto") and resolve a plain-language selection against it."""

    policy_number: str
    customer_name: str
    line_of_business: str
    vehicle_description: str | None = None


class ClaimsIntakeState(BaseModel):
    """Everything the Agent needs to resume a claims-intake conversation on the next turn."""

    status: ClaimsIntakeStatus = ClaimsIntakeStatus.NEW

    customer_name: str | None = None
    candidates: list[PolicyCandidate] = Field(default_factory=list)

    policy_number: str | None = None
    event_date: str | None = None
    event_time: str | None = None
    event_location: str | None = None
    loss_type: str | None = None
    loss_description: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    injuries_reported: bool | None = None
    third_parties_involved: bool | None = None

    policy_validated: bool = False
    policy_active: bool | None = None
    payment_current: bool | None = None
    holder_name: str | None = None
    coverage_type: str | None = None
    coverage_limit: float | None = None
    coverage_deductible: float | None = None

    confirmed: bool | None = None

    claim_reference: str | None = None
    adjuster_assigned: str | None = None

    # Tracks which field the last question was about, so a free-text answer with no
    # recognizable structure (e.g. a loss description) can be attributed correctly.
    last_asked_field: str | None = None

    # Tracks every field a combined/grouped question (state.FIELD_GROUPS) just asked about in
    # one message — distinct from last_asked_field (always a single field) because a grouped
    # question like "what date, where, and what type of loss?" needs event_location's
    # free-text fallback to apply even though event_date (a different field in the same group)
    # is what actually set last_asked_field. See extraction.extract_fields.
    last_asked_group: list[str] = Field(default_factory=list)


# Order matters: also the order fields are asked for. Grouped (PBI-04-04's "natural
# conversation" requirement — never ask one trivial fact at a time when several belong
# together) rather than one field per group like the original PBI-01-05 flow. "customer_name"
# is NOT one of these groups — it is handled as its own priority step, before any of these,
# by src.agents.claims.workflow._handle_collecting_information, so customer discovery (asking
# the name, then immediately looking it up) happens right after the name is given rather than
# being deferred until every other incident detail has also been collected.
FIELD_GROUPS: tuple[tuple[str, ...], ...] = (
    ("event_date", "event_location", "loss_type"),
    ("loss_description",),
    ("contact_phone",),
    ("injuries_reported", "third_parties_involved"),
)

# Every required field across every group, in order — used by missing_required_fields().
REQUIRED_FIELDS: tuple[str, ...] = tuple(field for group in FIELD_GROUPS for field in group)

FIELD_PROMPTS: dict[str, dict[Language, str]] = {
    "customer_name": {
        "es-MX": "¿Cuál es tu nombre completo? Así puedo buscar tus pólizas.",
        "en": "What is your full name? I'll use it to look up your policies.",
    },
    "event_date": {
        "es-MX": "¿Qué día ocurrió el incidente? (AAAA-MM-DD)",
        "en": "What date did the incident occur? (YYYY-MM-DD)",
    },
    "event_location": {
        "es-MX": "¿Dónde ocurrió el incidente?",
        "en": "Where did the incident take place?",
    },
    "loss_type": {
        "es-MX": (
            "¿Qué tipo de siniestro fue (colisión, robo, incendio, daño por agua, clima, "
            "vandalismo, otro)?"
        ),
        "en": (
            "What type of loss is this (e.g., collision, theft, fire, water damage, weather, "
            "vandalism, other)?"
        ),
    },
    "loss_description": {
        "es-MX": "¿Podrías describir brevemente qué sucedió?",
        "en": "Could you briefly describe what happened?",
    },
    "contact_phone": {
        "es-MX": "¿Cuál es el mejor teléfono para contactarte?",
        "en": "What is the best phone number to reach you?",
    },
    "injuries_reported": {
        "es-MX": "¿Hubo personas lesionadas? (sí/no)",
        "en": "Were there any injuries involved? (yes/no)",
    },
    "third_parties_involved": {
        "es-MX": "¿Estuvieron involucrados terceros? (sí/no)",
        "en": "Were any third parties involved? (yes/no)",
    },
}

# Fields the state machine will opportunistically capture when volunteered, but never asks for.
OPTIONAL_FIELDS: tuple[str, ...] = ("event_time", "contact_email")


def missing_required_fields(state: ClaimsIntakeState) -> list[str]:
    """Incident-detail fields still unanswered, in the order they should be asked. Does not
    include customer_name, which src.agents.claims.workflow._handle_collecting_information
    handles as its own priority step before ever calling this."""
    return [field for field in REQUIRED_FIELDS if getattr(state, field) is None]


def next_question_group(missing: list[str]) -> list[str]:
    """The next batch of missing fields that belong in a single combined question, per
    FIELD_GROUPS — never more than one group's worth at a time."""
    missing_set = set(missing)
    for group in FIELD_GROUPS:
        group_missing = [field for field in group if field in missing_set]
        if group_missing:
            return group_missing
    return []

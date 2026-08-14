"""Shared semantic-understanding contracts (PBI-14-03).

One structured shape (SemanticInterpretation) is reused by Claims, Broker Services, and
Commercial Intake — a single shared abstraction, never three independent conversational
engines (PBI-14-03 section 3). Each domain supplies its own typed `entities` submodel
(ClaimsEntities / BrokerEntities / CommercialEntities) matching that Agent's own real
ClaimsIntakeState / BrokerInquiryState / CommercialIntakeState fields (src.agents.claims.state,
src.agents.broker.state, src.agents.commercial.state) — never invented fields.

Commercial's industry/location/insured_value are the one addition beyond an existing state
field (PBI-14-01's finding that useful intake/qualification concepts are currently dropped).
They are intake/qualification data only: CommercialIntakeAgent must never use them to price,
quote, underwrite, or approve risk/coverage (CLAUDE.md §2) — nothing in this module or its
callers is authorized to treat them as anything more than context carried alongside the
existing required lead fields.

No field on any model here may ever hold chain-of-thought or private model reasoning
(CLAUDE.md §10) — only the structured, safe-to-persist result of one interpretation call. These
models are also never the source of a business fact (CLAUDE.md §3): entities are candidates a
deterministic merge (src.agents.shared.semantic_merge) may adopt only when the equivalent
deterministic extractor left the field empty, and confirmation/coverage/policy/claim/commission
truth always still comes from a Tool.
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, Field

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class ClaimsEntities(BaseModel):
    """The free-text/ambiguous subset of ClaimsIntakeState this layer may help fill — never
    policy_number/line_of_business/coverage/policy_validated/claim_reference/adjuster_assigned,
    which only ever come from a Tool result, never from language understanding."""

    customer_name: str | None = None
    event_date: str | None = None
    event_time: str | None = None
    event_location: str | None = None
    loss_type: str | None = None
    loss_description: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    injuries_reported: bool | None = None
    third_parties_involved: bool | None = None
    vehicle_drivable: bool | None = None
    property_habitable: bool | None = None


class BrokerEntities(BaseModel):
    """The free-text/ambiguous subset of BrokerInquiryState this layer may help fill — never
    broker_id/broker_active/policy_status/transaction_status/commission_amount/commission_status/
    payment_request_reference, which only ever come from a Tool result."""

    broker_name: str | None = None
    policy_number: str | None = None
    transaction_reference: str | None = None
    commission_period: str | None = None
    wants_payment_request: bool | None = None


class CommercialEntities(BaseModel):
    """The free-text/ambiguous subset of CommercialIntakeState this layer may help fill, plus
    industry/location/insured_value — additional qualification-only context (see module
    docstring); never lead_reference, which only ever comes from a Tool result."""

    company_name: str | None = None
    contact_name: str | None = None
    preferred_contact_channel: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    insurance_need: str | None = None
    risk_description: str | None = None
    industry: str | None = None
    location: str | None = None
    insured_value: str | None = None


class SemanticInterpretation(BaseModel):
    """The one structured shape every domain's semantic interpretation call returns (PBI-14-03
    section 3). No chain-of-thought/private-reasoning field exists here, and none may ever be
    added — CLAUDE.md §10 forbids persisting or exposing hidden model reasoning."""

    intent: str
    intent_confidence: float = Field(ge=0.0, le=1.0)
    alternative_intents: list[str] = Field(default_factory=list)
    confirmation: bool | None = None
    corrections: dict[str, str] = Field(default_factory=dict)
    already_answered: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)


class ClaimsSemanticInterpretation(SemanticInterpretation):
    entities: ClaimsEntities = Field(default_factory=ClaimsEntities)


class BrokerSemanticInterpretation(SemanticInterpretation):
    entities: BrokerEntities = Field(default_factory=BrokerEntities)


class CommercialSemanticInterpretation(SemanticInterpretation):
    entities: CommercialEntities = Field(default_factory=CommercialEntities)


# ---------------------------------------------------------------------------------------------
# PBI-14-04: universal, pre-routing turn interpretation.
# ---------------------------------------------------------------------------------------------
#
# PBI-14-03 made semantic interpretation real, but it only ran *inside* whichever specialist
# Agent the Supervisor's keyword-only RuleBasedIntentResolver had already selected — a message
# with no domain keyword at all (e.g. "un camión me pegó por atrás") never reached a specialist
# whose own semantic layer would have understood it; it was misrouted to FallbackAgent before
# any LLM call ever ran. TurnInterpretation is the ONE per-turn structured interpretation now
# produced BEFORE routing (src.supervisor.semantic_routing) and reused, unchanged, by whichever
# specialist the deterministic Supervisor selects — never a second call for the same turn.
#
# intent is one of the four wire-level strings below (never an IntentCategory enum value
# directly — this schema must stay independent of src.supervisor.models so
# src.agents.shared stays the shared/foundational layer, not a re-export of Supervisor types).


class AlternativeIntent(BaseModel):
    """One runner-up classification the model considered — never chain-of-thought, only the
    candidate label and its own confidence, the same shape intent/intent_confidence already
    use."""

    intent: str
    confidence: float = Field(ge=0.0, le=1.0)


class TurnInterpretation(BaseModel):
    """The one structured shape produced by the ONE per-turn semantic call, BEFORE Supervisor
    routing (PBI-14-04). Carries routing signal (intent/confidence/alternatives/
    requires_clarification) and, in the SAME call, whichever domain's entities are confidently
    inferable — never a second LLM round trip to get domain entities after routing.

    Only the entities field matching `intent` should ever be populated by a well-behaved model;
    src.agents.shared.semantic_models.to_domain_interpretation reads only the matching one
    regardless. No field here may ever hold chain-of-thought or private model reasoning
    (CLAUDE.md §10) — routing_reason is a short, safe, user-irrelevant classification label
    ("User is reporting damage from a vehicle collision."), never step-by-step reasoning text.
    """

    intent: str
    intent_confidence: float = Field(ge=0.0, le=1.0)
    alternative_intents: list[AlternativeIntent] = Field(default_factory=list)
    requires_clarification: bool = False
    confirmation: bool | None = None
    corrections: dict[str, str] = Field(default_factory=dict)
    already_answered: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    routing_reason: str | None = None
    claims_entities: ClaimsEntities | None = None
    broker_entities: BrokerEntities | None = None
    commercial_entities: CommercialEntities | None = None


# Wire-level intent labels the shared turn-interpretation prompt is instructed to return —
# deliberately distinct strings from src.supervisor.models.IntentCategory's own enum values
# (upper-case "CLAIMS"/"BROKER"/"COMMERCIAL"/"UNKNOWN") so this module never needs to import
# Supervisor's enum; src.supervisor.semantic_routing owns the mapping between the two.
TURN_INTENT_CLAIMS = "claims"
TURN_INTENT_BROKER = "broker_services"
TURN_INTENT_COMMERCIAL = "commercial_intake"
TURN_INTENT_UNKNOWN = "unknown"


def _empty_domain_interpretation(schema_type: type[SchemaT]) -> SchemaT:  # noqa: UP047
    return schema_type(intent=TURN_INTENT_UNKNOWN, intent_confidence=0.0)


def to_domain_interpretation(  # noqa: UP047
    turn: TurnInterpretation | None, schema_type: type[SchemaT]
) -> SchemaT:
    """Adapts a shared TurnInterpretation into the legacy per-domain
    Claims/Broker/CommercialSemanticInterpretation shape each Agent's own
    advance_*_intake/advance_*_inquiry workflow function already expects (unchanged since
    PBI-14-03) — so reusing the Supervisor's one pre-routing interpretation requires no change
    to any workflow.py signature. Picks whichever of claims_entities/broker_entities/
    commercial_entities matches schema_type; `turn=None` (e.g. a direct unit-test call with no
    Supervisor in front of it) degrades to the same safe empty interpretation
    src.agents.shared.semantic_interpreter._empty already returns on a genuine LLM/parse
    failure."""
    if turn is None:
        return _empty_domain_interpretation(schema_type)

    entities: BaseModel | None
    if schema_type is ClaimsSemanticInterpretation:
        entities = turn.claims_entities
    elif schema_type is BrokerSemanticInterpretation:
        entities = turn.broker_entities
    elif schema_type is CommercialSemanticInterpretation:
        entities = turn.commercial_entities
    else:
        entities = None

    kwargs: dict[str, object] = {
        "intent": turn.intent,
        "intent_confidence": turn.intent_confidence,
        "alternative_intents": [a.intent for a in turn.alternative_intents],
        "confirmation": turn.confirmation,
        "corrections": turn.corrections,
        "already_answered": turn.already_answered,
        "missing_information": turn.missing_information,
    }
    if entities is not None:
        kwargs["entities"] = entities
    return schema_type(**kwargs)

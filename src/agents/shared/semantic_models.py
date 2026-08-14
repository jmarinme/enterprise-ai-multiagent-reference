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

from pydantic import BaseModel, Field


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

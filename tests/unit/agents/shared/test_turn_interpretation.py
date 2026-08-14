"""Unit tests for TurnInterpretation and to_domain_interpretation (PBI-14-04): the shared,
pre-routing structured shape and its adapter into each domain's legacy
Claims/Broker/CommercialSemanticInterpretation shape, so no workflow.py signature had to change
to reuse it.
"""

from src.agents.shared.semantic_models import (
    AlternativeIntent,
    BrokerSemanticInterpretation,
    ClaimsEntities,
    ClaimsSemanticInterpretation,
    CommercialSemanticInterpretation,
    TurnInterpretation,
    to_domain_interpretation,
)


def test_to_domain_interpretation_picks_only_the_matching_entities() -> None:
    # A well-behaved model (per the shared prompt's own instructions) only ever populates the
    # ONE entities object matching its primary `intent` — the other two stay null.
    turn = TurnInterpretation(
        intent="claims",
        intent_confidence=0.9,
        claims_entities=ClaimsEntities(loss_type="collision"),
        broker_entities=None,
        commercial_entities=None,
    )

    claims_interpretation = to_domain_interpretation(turn, ClaimsSemanticInterpretation)
    broker_interpretation = to_domain_interpretation(turn, BrokerSemanticInterpretation)
    commercial_interpretation = to_domain_interpretation(turn, CommercialSemanticInterpretation)

    assert claims_interpretation.entities.loss_type == "collision"
    # Requesting a domain the model did not populate degrades to empty entities, never an error
    # and never fabricated data — e.g. a low-confidence-fallback turn routed to a different
    # agent than the one the LLM originally classified.
    assert broker_interpretation.entities.broker_name is None
    assert commercial_interpretation.entities.company_name is None


def test_to_domain_interpretation_preserves_confidence_and_confirmation() -> None:
    turn = TurnInterpretation(intent="claims", intent_confidence=0.77, confirmation=True)

    interpretation = to_domain_interpretation(turn, ClaimsSemanticInterpretation)

    assert interpretation.intent_confidence == 0.77
    assert interpretation.confirmation is True


def test_to_domain_interpretation_flattens_alternative_intents_to_plain_strings() -> None:
    turn = TurnInterpretation(
        intent="broker_services",
        intent_confidence=0.5,
        alternative_intents=[AlternativeIntent(intent="commercial_intake", confidence=0.45)],
    )

    interpretation = to_domain_interpretation(turn, BrokerSemanticInterpretation)

    assert interpretation.alternative_intents == ["commercial_intake"]


def test_to_domain_interpretation_degrades_safely_when_turn_is_none() -> None:
    """Mirrors src.agents.shared.semantic_interpreter._empty's own fallback shape — used when a
    specialist Agent is called directly with no Supervisor in front of it."""
    interpretation = to_domain_interpretation(None, ClaimsSemanticInterpretation)

    assert interpretation.intent == "unknown"
    assert interpretation.intent_confidence == 0.0
    assert interpretation.entities == ClaimsEntities()


def test_turn_interpretation_schema_never_exposes_chain_of_thought() -> None:
    """CLAUDE.md §10 / PBI-14-04 section 4: routing_reason is a short safe label, never a
    reasoning field — assert no such field exists on the shared shape at all."""
    schema = TurnInterpretation.model_json_schema()

    forbidden_terms = ("reasoning", "chain_of_thought", "thought", "rationale", "thinking")
    property_names = {name.lower() for name in schema.get("properties", {})}
    assert not (property_names & set(forbidden_terms))

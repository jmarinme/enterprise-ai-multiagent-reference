"""Unit tests for the shared semantic-entity merge (PBI-14-03 section 7): deterministic
extraction always wins, semantic entities only ever fill a genuine gap, and low-confidence
interpretations are never applied at all.
"""

from src.agents.claims.state import ClaimsIntakeState
from src.agents.shared.semantic_merge import MIN_CONFIDENCE_TO_APPLY, apply_semantic_entities
from src.agents.shared.semantic_models import ClaimsEntities


def test_fills_only_fields_left_empty_by_deterministic_extraction() -> None:
    state = ClaimsIntakeState(event_location="Reforma")
    entities = ClaimsEntities(event_location="A different place", loss_description="Choqué.")

    updated, applied = apply_semantic_entities(
        state, entities, intent_confidence=0.9, fields=("event_location", "loss_description")
    )

    # Already-set deterministic value is never overwritten.
    assert updated.event_location == "Reforma"
    # Genuinely empty field is filled.
    assert updated.loss_description == "Choqué."
    assert applied == ["loss_description"]


def test_never_applies_below_the_minimum_confidence_threshold() -> None:
    state = ClaimsIntakeState()
    entities = ClaimsEntities(loss_description="Choqué.")

    updated, applied = apply_semantic_entities(
        state,
        entities,
        intent_confidence=MIN_CONFIDENCE_TO_APPLY - 0.01,
        fields=("loss_description",),
    )

    assert updated.loss_description is None
    assert applied == []


def test_applies_at_exactly_the_minimum_confidence_threshold() -> None:
    state = ClaimsIntakeState()
    entities = ClaimsEntities(loss_description="Choqué.")

    updated, applied = apply_semantic_entities(
        state, entities, intent_confidence=MIN_CONFIDENCE_TO_APPLY, fields=("loss_description",)
    )

    assert updated.loss_description == "Choqué."
    assert applied == ["loss_description"]


def test_skips_fields_the_entities_model_left_empty_too() -> None:
    state = ClaimsIntakeState()
    entities = ClaimsEntities()

    updated, applied = apply_semantic_entities(
        state, entities, intent_confidence=1.0, fields=("loss_description", "event_location")
    )

    assert updated.loss_description is None
    assert updated.event_location is None
    assert applied == []

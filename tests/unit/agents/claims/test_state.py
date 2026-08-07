"""Unit tests for the claims-intake state model: defaults, missing-field computation, and
that every required field has a corresponding prompt.
"""

from src.agents.claims.state import (
    FIELD_PROMPTS,
    OPTIONAL_FIELDS,
    REQUIRED_FIELDS,
    ClaimsIntakeState,
    ClaimsIntakeStatus,
    missing_required_fields,
)


def test_fresh_state_defaults_to_new_status_with_no_fields_set() -> None:
    state = ClaimsIntakeState()

    assert state.status == ClaimsIntakeStatus.NEW
    assert state.policy_validated is False
    assert missing_required_fields(state) == list(REQUIRED_FIELDS)


def test_every_required_field_has_a_prompt() -> None:
    for field in REQUIRED_FIELDS:
        assert field in FIELD_PROMPTS
        assert FIELD_PROMPTS[field]


def test_optional_fields_are_never_asked_for() -> None:
    assert set(OPTIONAL_FIELDS).isdisjoint(REQUIRED_FIELDS)
    for field in OPTIONAL_FIELDS:
        assert field not in FIELD_PROMPTS


def test_missing_required_fields_shrinks_as_fields_are_filled() -> None:
    state = ClaimsIntakeState(policy_number="SYN-POL-0001", event_date="2026-08-01")

    missing = missing_required_fields(state)

    assert "policy_number" not in missing
    assert "event_date" not in missing
    assert "event_location" in missing


def test_missing_required_fields_treats_false_as_answered() -> None:
    state = ClaimsIntakeState(
        policy_number="SYN-POL-0001",
        event_date="2026-08-01",
        event_location="Main St",
        loss_type="collision",
        loss_description="Rear-ended.",
        contact_name="Jane",
        contact_phone="555-123-4567",
        injuries_reported=False,
        third_parties_involved=False,
    )

    assert missing_required_fields(state) == []

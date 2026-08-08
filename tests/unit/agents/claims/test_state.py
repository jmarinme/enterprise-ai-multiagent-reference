"""Unit tests for the claims-intake state model: defaults, LOB-aware missing-field
computation, and that every required field has a corresponding prompt (PBI-05-01: field sets
are now a function of line_of_business, not a fixed module-level tuple).
"""

from src.agents.claims.state import (
    FIELD_PROMPTS,
    OPTIONAL_FIELDS,
    ClaimsIntakeState,
    ClaimsIntakeStatus,
    field_groups_for,
    missing_required_fields,
    required_fields_for,
)


def test_fresh_state_defaults_to_new_status_with_no_fields_set() -> None:
    state = ClaimsIntakeState()

    assert state.status == ClaimsIntakeStatus.NEW
    assert state.policy_validated is False
    assert missing_required_fields(state) == list(required_fields_for(None))


def test_every_required_field_has_a_prompt_for_every_known_line_of_business() -> None:
    for line_of_business in (None, "auto", "property"):
        for field in required_fields_for(line_of_business):
            assert field in FIELD_PROMPTS
            assert FIELD_PROMPTS[field]


def test_optional_fields_are_never_asked_for() -> None:
    for line_of_business in (None, "auto", "property"):
        required = required_fields_for(line_of_business)
        assert set(OPTIONAL_FIELDS).isdisjoint(required)
    for field in OPTIONAL_FIELDS:
        assert field not in FIELD_PROMPTS


def test_auto_profile_includes_vehicle_drivable_but_not_property_habitable() -> None:
    required = required_fields_for("auto")

    assert "vehicle_drivable" in required
    assert "property_habitable" not in required


def test_property_profile_includes_property_habitable_but_not_vehicle_drivable() -> None:
    required = required_fields_for("property")

    assert "property_habitable" in required
    assert "vehicle_drivable" not in required


def test_unknown_or_missing_line_of_business_asks_only_common_fields() -> None:
    required = required_fields_for(None)

    assert "vehicle_drivable" not in required
    assert "property_habitable" not in required


def test_missing_required_fields_shrinks_as_fields_are_filled() -> None:
    state = ClaimsIntakeState(policy_number="SYN-POL-0001", event_date="2026-08-01")

    missing = missing_required_fields(state)

    assert "event_date" not in missing
    assert "event_location" in missing


def test_missing_required_fields_treats_false_as_answered() -> None:
    state = ClaimsIntakeState(
        policy_number="SYN-POL-0001",
        event_date="2026-08-01",
        event_location="Main St",
        loss_type="collision",
        loss_description="Rear-ended.",
        customer_name="Jane",
        contact_phone="555-123-4567",
        injuries_reported=False,
        third_parties_involved=False,
    )

    assert missing_required_fields(state) == []


def test_missing_required_fields_for_auto_includes_vehicle_drivable_until_answered() -> None:
    state = ClaimsIntakeState(
        line_of_business="auto",
        policy_number="SYN-POL-1002",
        event_date="2026-08-07",
        event_location="Reforma",
        loss_type="collision",
        loss_description="Rear-ended.",
        contact_phone="555-123-4567",
        injuries_reported=False,
        third_parties_involved=False,
    )

    assert missing_required_fields(state) == ["vehicle_drivable"]

    answered = state.model_copy(update={"vehicle_drivable": True})
    assert missing_required_fields(answered) == []


def test_field_groups_for_appends_exactly_one_lob_specific_group() -> None:
    common_group_count = len(field_groups_for(None))

    assert len(field_groups_for("auto")) == common_group_count + 1
    assert len(field_groups_for("property")) == common_group_count + 1

"""Unit tests for the commercial-intake state model: defaults and ordered missing-field
computation, including the preferred-contact-channel-dependent contact detail.
"""

from src.agents.commercial.state import (
    FIELD_PROMPTS,
    CommercialIntakeState,
    CommercialIntakeStatus,
    missing_required_fields,
)


def test_fresh_state_defaults_to_new_status_with_no_fields_set() -> None:
    state = CommercialIntakeState()

    assert state.status == CommercialIntakeStatus.NEW
    assert missing_required_fields(state) == ["company_name"]


def test_every_field_prompt_field_name_matches_a_real_state_attribute() -> None:
    state = CommercialIntakeState()
    for field in FIELD_PROMPTS:
        assert hasattr(state, field)


def test_missing_required_fields_asks_one_field_at_a_time_in_order() -> None:
    state = CommercialIntakeState(company_name="Acme Co")

    assert missing_required_fields(state) == ["contact_name"]


def test_missing_required_fields_asks_for_email_when_channel_is_email() -> None:
    state = CommercialIntakeState(
        company_name="Acme Co", contact_name="Jane", preferred_contact_channel="email"
    )

    assert missing_required_fields(state) == ["contact_email"]


def test_missing_required_fields_asks_for_phone_when_channel_is_phone() -> None:
    state = CommercialIntakeState(
        company_name="Acme Co", contact_name="Jane", preferred_contact_channel="phone"
    )

    assert missing_required_fields(state) == ["contact_phone"]


def test_missing_required_fields_moves_on_once_contact_detail_is_known() -> None:
    state = CommercialIntakeState(
        company_name="Acme Co",
        contact_name="Jane",
        preferred_contact_channel="email",
        contact_email="jane@example.com",
    )

    assert missing_required_fields(state) == ["insurance_need"]


def test_missing_required_fields_is_empty_once_everything_is_collected() -> None:
    state = CommercialIntakeState(
        company_name="Acme Co",
        contact_name="Jane",
        preferred_contact_channel="email",
        contact_email="jane@example.com",
        insurance_need="general liability",
        risk_description="A small consulting business.",
    )

    assert missing_required_fields(state) == []

"""Unit tests for deterministic commercial-intake field extraction. No LLM involved — every
case here must be resolvable by regex/keyword rules alone (MockLLMProvider cannot do real NLU).
"""

from src.agents.commercial.extraction import extract_fields
from src.agents.commercial.state import CommercialIntakeState


def test_extracts_email() -> None:
    state = extract_fields("you can reach me at jane@example.com", CommercialIntakeState())

    assert state.contact_email == "jane@example.com"


def test_extracts_phone_number() -> None:
    state = extract_fields("call me at 555-123-4567", CommercialIntakeState())

    assert state.contact_phone is not None
    assert "555" in state.contact_phone


def test_detects_email_channel_preference() -> None:
    state = extract_fields("email works best for me", CommercialIntakeState())

    assert state.preferred_contact_channel == "email"


def test_detects_phone_channel_preference() -> None:
    state = extract_fields("please call me", CommercialIntakeState())

    assert state.preferred_contact_channel == "phone"


def test_detects_insurance_need_from_keyword() -> None:
    state = extract_fields("I need general liability coverage", CommercialIntakeState())

    assert state.insurance_need == "general liability"


def test_free_text_fallback_fills_the_last_asked_free_text_field() -> None:
    state = CommercialIntakeState(last_asked_field="company_name")

    updated = extract_fields("Acme Consulting LLC", state)

    assert updated.company_name == "Acme Consulting LLC"


def test_free_text_fallback_does_not_apply_to_structured_fields() -> None:
    """An unrecognizable answer to a structured question (e.g. contact channel) must leave the
    field missing so the workflow re-prompts, not silently accept unrelated text."""
    state = CommercialIntakeState(last_asked_field="preferred_contact_channel")

    updated = extract_fields("whatever is easiest for you", state)

    assert updated.preferred_contact_channel is None


def test_free_text_fallback_never_overwrites_an_already_filled_field() -> None:
    state = CommercialIntakeState(last_asked_field="company_name", company_name="already set")

    updated = extract_fields("something else entirely", state)

    assert updated.company_name == "already set"


def test_free_text_fallback_is_skipped_when_a_structured_field_matched_instead() -> None:
    state = CommercialIntakeState(last_asked_field="risk_description")

    updated = extract_fields("jane@example.com", state)

    assert updated.risk_description is None
    assert updated.contact_email == "jane@example.com"

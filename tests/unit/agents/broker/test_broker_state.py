"""Unit tests for the broker-services state model: defaults, per-inquiry-type missing-field
computation, and the combined-prompt behavior for the commission inquiry.
"""

from src.agents.broker.state import (
    FIELD_PROMPTS,
    REQUIRED_FIELDS_BY_INQUIRY,
    BrokerInquiryState,
    BrokerInquiryStatus,
    BrokerInquiryType,
    missing_required_fields,
    prompt_for_missing,
)


def test_fresh_state_defaults_to_new_status_with_no_inquiry_type() -> None:
    state = BrokerInquiryState()

    assert state.status == BrokerInquiryStatus.NEW
    assert state.inquiry_type is None
    assert missing_required_fields(state) == []


def test_every_required_field_across_every_inquiry_type_has_a_prompt() -> None:
    for fields in REQUIRED_FIELDS_BY_INQUIRY.values():
        for field in fields:
            assert field in FIELD_PROMPTS
            assert FIELD_PROMPTS[field]


def test_missing_required_fields_is_scoped_to_the_current_inquiry_type() -> None:
    state = BrokerInquiryState(inquiry_type=BrokerInquiryType.POLICY_STATUS)

    assert missing_required_fields(state) == ["policy_number"]


def test_missing_required_fields_shrinks_as_fields_are_filled() -> None:
    state = BrokerInquiryState(
        inquiry_type=BrokerInquiryType.COMMISSION, broker_id="SYN-BRK-0001"
    )

    assert missing_required_fields(state) == ["commission_period"]


def test_prompt_for_missing_combines_both_commission_fields_in_one_message() -> None:
    prompt = prompt_for_missing(["broker_id", "commission_period"], "en")

    assert "broker ID" in prompt
    assert "period" in prompt


def test_prompt_for_missing_a_single_field_uses_its_own_prompt() -> None:
    prompt = prompt_for_missing(["policy_number"], "en")

    assert prompt == FIELD_PROMPTS["policy_number"]["en"]

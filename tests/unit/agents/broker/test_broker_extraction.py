"""Unit tests for deterministic broker-services field extraction. No LLM involved — every case
here must be resolvable by regex/keyword rules alone (MockLLMProvider cannot do real NLU).
"""

from src.agents.broker.extraction import extract_fields
from src.agents.broker.state import BrokerInquiryState, BrokerInquiryType


def test_detects_policy_status_inquiry_from_keyword() -> None:
    state = extract_fields("I want to know the status of a policy.", BrokerInquiryState())

    assert state.inquiry_type == BrokerInquiryType.POLICY_STATUS


def test_detects_commission_inquiry_from_keyword() -> None:
    state = extract_fields("I need to check my commissions.", BrokerInquiryState())

    assert state.inquiry_type == BrokerInquiryType.COMMISSION


def test_detects_transaction_inquiry_from_keyword() -> None:
    state = extract_fields("What is the status of my transaction?", BrokerInquiryState())

    assert state.inquiry_type == BrokerInquiryType.TRANSACTION_STATUS


def test_commission_keyword_takes_priority_over_policy_keyword() -> None:
    state = extract_fields(
        "I want to check my commission for this policy.", BrokerInquiryState()
    )

    assert state.inquiry_type == BrokerInquiryType.COMMISSION


def test_inquiry_type_is_not_overwritten_once_set() -> None:
    state = BrokerInquiryState(inquiry_type=BrokerInquiryType.POLICY_STATUS)

    updated = extract_fields("I need to check my commissions.", state)

    assert updated.inquiry_type == BrokerInquiryType.POLICY_STATUS


def test_extracts_policy_number() -> None:
    state = extract_fields("it's syn-pol-0001", BrokerInquiryState())

    assert state.policy_number == "SYN-POL-0001"


def test_extracts_broker_id() -> None:
    state = extract_fields("my broker id is SYN-BRK-0001", BrokerInquiryState())

    assert state.broker_id == "SYN-BRK-0001"


def test_extracts_transaction_reference() -> None:
    state = extract_fields("reference SYN-TXN-0001", BrokerInquiryState())

    assert state.transaction_reference == "SYN-TXN-0001"


def test_extracts_commission_period_with_quarter_format() -> None:
    state = extract_fields("please check 2026-Q1", BrokerInquiryState())

    assert state.commission_period == "2026-Q1"


def test_broker_id_and_policy_number_never_cross_contaminate() -> None:
    state = extract_fields("SYN-BRK-0001 and SYN-POL-0001", BrokerInquiryState())

    assert state.broker_id == "SYN-BRK-0001"
    assert state.policy_number == "SYN-POL-0001"


def test_yes_no_answer_is_only_interpreted_for_the_last_asked_yes_no_field() -> None:
    state = BrokerInquiryState(last_asked_field="wants_payment_request")

    updated = extract_fields("yes", state)

    assert updated.wants_payment_request is True


def test_no_answer_sets_wants_payment_request_false() -> None:
    state = BrokerInquiryState(last_asked_field="wants_payment_request")

    updated = extract_fields("no thanks", state)

    assert updated.wants_payment_request is False


def test_payment_request_keyword_sets_wants_payment_request_without_being_asked() -> None:
    state = extract_fields(
        "I'd like to request payment for my commission.", BrokerInquiryState()
    )

    assert state.wants_payment_request is True


def test_wants_payment_request_is_never_overwritten_once_set() -> None:
    state = BrokerInquiryState(wants_payment_request=False)

    updated = extract_fields("request payment please", state)

    assert updated.wants_payment_request is False

"""Unit tests for the broker-services state machine (advance_broker_inquiry), driven end-to-end
through real synthetic Tools via ToolExecutor. Covers policy/transaction/commission scenarios,
the not-found retry path, and duplicate payment-request prevention.
"""

import re

from src.agents.broker.state import BrokerInquiryState, BrokerInquiryStatus
from src.agents.broker.workflow import advance_broker_inquiry
from src.services.tools.broker_account_lookup_tool import BrokerAccountLookupTool
from src.services.tools.commission_lookup_tool import CommissionLookupTool
from src.services.tools.commission_payment_request_tool import CommissionPaymentRequestTool
from src.services.tools.payment_status_tool import PaymentStatusTool
from src.services.tools.policy_lookup_tool import PolicyLookupTool
from src.services.tools.transaction_status_tool import TransactionStatusTool
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry

_PAYMENT_REQUEST_REFERENCE_PATTERN = re.compile(r"SYN-PAYREQ-\d{4}-\d{4}")


def _build_executor() -> ToolExecutor:
    registry = InMemoryToolRegistry()
    registry.register(PolicyLookupTool())
    registry.register(PaymentStatusTool())
    registry.register(BrokerAccountLookupTool())
    registry.register(TransactionStatusTool())
    registry.register(CommissionLookupTool())
    registry.register(CommissionPaymentRequestTool())
    return ToolExecutor(tool_registry=registry)


async def test_new_conversation_asks_what_kind_of_help_is_needed() -> None:
    state, notices = await advance_broker_inquiry(
        BrokerInquiryState(), "hello", _build_executor(), language="en"
    )

    assert state.status == BrokerInquiryStatus.IDENTIFYING_REQUEST
    assert len(notices) == 1


async def test_policy_status_inquiry_asks_only_for_the_policy_number() -> None:
    state, notices = await advance_broker_inquiry(
        BrokerInquiryState(), "I want to know the status of a policy.", _build_executor(), language="en"
    )

    assert state.status == BrokerInquiryStatus.COLLECTING_INFORMATION
    assert notices == ["Please provide the synthetic policy number."]


async def test_full_policy_status_conversation_reports_status_and_payment() -> None:
    executor = _build_executor()
    state = BrokerInquiryState()

    state, _ = await advance_broker_inquiry(
        state, "I want to know the status of a policy.", executor, language="en"
    )
    state, notices = await advance_broker_inquiry(state, "SYN-POL-0001", executor, language="en")

    assert state.status == BrokerInquiryStatus.COMPLETED
    assert state.policy_status == "active"
    assert state.policy_payment_current is True
    combined = " ".join(notices).lower()
    assert "active" in combined
    assert "up to date" in combined
    # The fact is stated once by the lookup, not repeated by a same-turn completion summary.
    assert combined.count("policy syn-pol-0001 status") == 1


async def test_unknown_policy_number_blocks_and_asks_to_recheck() -> None:
    executor = _build_executor()
    state = BrokerInquiryState()
    state, _ = await advance_broker_inquiry(
        state, "I want to know the status of a policy.", executor, language="en"
    )

    state, notices = await advance_broker_inquiry(state, "SYN-POL-9999", executor, language="en")

    assert state.status == BrokerInquiryStatus.LOOKING_UP_DATA
    assert "could not find a policy" in " ".join(notices).lower()


async def test_correcting_policy_number_after_not_found_retries_lookup() -> None:
    executor = _build_executor()
    state = BrokerInquiryState()
    state, _ = await advance_broker_inquiry(
        state, "I want to know the status of a policy.", executor, language="en"
    )
    state, _ = await advance_broker_inquiry(state, "SYN-POL-9999", executor, language="en")

    state, notices = await advance_broker_inquiry(state, "sorry, SYN-POL-0001", executor, language="en")

    assert state.status == BrokerInquiryStatus.COMPLETED
    assert "could not find" not in " ".join(notices).lower()


async def test_transaction_status_inquiry_reports_status() -> None:
    executor = _build_executor()
    state = BrokerInquiryState()
    state, _ = await advance_broker_inquiry(
        state, "What is the status of my transaction?", executor, language="en"
    )

    state, notices = await advance_broker_inquiry(state, "SYN-TXN-0001", executor, language="en")

    assert state.status == BrokerInquiryStatus.COMPLETED
    assert state.transaction_status == "completed"
    assert "completed" in " ".join(notices).lower()


async def test_unknown_broker_id_blocks_commission_lookup() -> None:
    executor = _build_executor()
    state = BrokerInquiryState()
    state, _ = await advance_broker_inquiry(
        state, "I need to check my commissions.", executor, language="en"
    )

    state, notices = await advance_broker_inquiry(
        state, "SYN-BRK-9999 2026-Q1", executor, language="en"
    )

    assert state.status == BrokerInquiryStatus.LOOKING_UP_DATA
    assert "could not find a broker" in " ".join(notices).lower()


async def test_commission_already_paid_does_not_offer_a_payment_request() -> None:
    executor = _build_executor()
    state = BrokerInquiryState()
    state, _ = await advance_broker_inquiry(
        state, "I need to check my commissions.", executor, language="en"
    )

    state, notices = await advance_broker_inquiry(state, "SYN-BRK-0001 2026-Q2", executor, language="en")

    assert state.status == BrokerInquiryStatus.COMPLETED
    assert state.commission_status == "paid"
    combined = " ".join(notices).lower()
    assert "paid" in combined
    assert "request payment" not in combined


async def test_commission_pending_does_not_offer_a_payment_request() -> None:
    executor = _build_executor()
    state = BrokerInquiryState()
    state, _ = await advance_broker_inquiry(
        state, "I need to check my commissions.", executor, language="en"
    )

    state, notices = await advance_broker_inquiry(state, "SYN-BRK-0002 2026-Q1", executor, language="en")

    assert state.status == BrokerInquiryStatus.COMPLETED
    assert state.commission_status == "pending"
    assert "request payment" not in " ".join(notices).lower()


async def test_available_commission_asks_whether_to_request_payment() -> None:
    executor = _build_executor()
    state = BrokerInquiryState()
    state, _ = await advance_broker_inquiry(
        state, "I need to check my commissions.", executor, language="en"
    )

    state, notices = await advance_broker_inquiry(state, "SYN-BRK-0001 2026-Q1", executor, language="en")

    assert state.status == BrokerInquiryStatus.READY_TO_RESPOND
    assert state.last_asked_field == "wants_payment_request"
    assert "would you like to request payment" in " ".join(notices).lower()


async def test_confirming_payment_request_registers_it_with_a_synthetic_reference() -> None:
    executor = _build_executor()
    state = BrokerInquiryState()
    state, _ = await advance_broker_inquiry(
        state, "I need to check my commissions.", executor, language="en"
    )
    state, _ = await advance_broker_inquiry(state, "SYN-BRK-0001 2026-Q1", executor, language="en")

    state, notices = await advance_broker_inquiry(state, "yes", executor, language="en")

    assert state.status == BrokerInquiryStatus.PAYMENT_REQUEST_REGISTERED
    assert state.payment_request_reference is not None
    assert _PAYMENT_REQUEST_REFERENCE_PATTERN.search(state.payment_request_reference)
    assert state.payment_request_reference in " ".join(notices)


async def test_declining_payment_request_completes_without_registering_one() -> None:
    executor = _build_executor()
    state = BrokerInquiryState()
    state, _ = await advance_broker_inquiry(
        state, "I need to check my commissions.", executor, language="en"
    )
    state, _ = await advance_broker_inquiry(state, "SYN-BRK-0001 2026-Q1", executor, language="en")

    state, _notices = await advance_broker_inquiry(state, "no", executor, language="en")

    assert state.status == BrokerInquiryStatus.COMPLETED
    assert state.payment_request_reference is None


async def test_a_message_after_payment_request_registered_does_not_submit_a_second_request() -> (
    None
):
    executor = _build_executor()
    state = BrokerInquiryState()
    state, _ = await advance_broker_inquiry(
        state, "I need to check my commissions.", executor, language="en"
    )
    state, _ = await advance_broker_inquiry(state, "SYN-BRK-0001 2026-Q1", executor, language="en")
    state, _ = await advance_broker_inquiry(state, "yes", executor, language="en")
    original_reference = state.payment_request_reference

    state, notices = await advance_broker_inquiry(state, "thanks!", executor, language="en")

    assert state.payment_request_reference == original_reference
    assert state.status == BrokerInquiryStatus.PAYMENT_REQUEST_REGISTERED
    assert "already registered" in " ".join(notices).lower()


async def test_ambiguous_first_message_asks_which_kind_of_help_is_needed() -> None:
    state, notices = await advance_broker_inquiry(
        BrokerInquiryState(), "hi there", _build_executor(), language="en"
    )

    assert state.inquiry_type is None
    assert "what would you like help with" in " ".join(notices).lower()

"""Unit tests for the commercial-intake state machine (advance_commercial_intake), driven
end-to-end through the real LeadRegistrationTool via ToolExecutor.
"""

import re

from src.agents.commercial.state import CommercialIntakeState, CommercialIntakeStatus
from src.agents.commercial.workflow import advance_commercial_intake
from src.services.tools.lead_registration_tool import LeadRegistrationTool
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry

_LEAD_REFERENCE_PATTERN = re.compile(r"^SYN-LEAD-\d{4}-\d{4}$")


def _build_executor() -> ToolExecutor:
    registry = InMemoryToolRegistry()
    registry.register(LeadRegistrationTool())
    return ToolExecutor(tool_registry=registry)


async def test_new_conversation_asks_for_company_name() -> None:
    state, notices = await advance_commercial_intake(
        CommercialIntakeState(),
        "I'd like a quote for new business coverage",
        _build_executor(),
        language="en",
    )

    assert state.status == CommercialIntakeStatus.COLLECTING_INFORMATION
    assert state.last_asked_field == "company_name"
    assert notices == ["What is your company or business name?"]


async def test_full_multi_turn_conversation_registers_a_synthetic_lead() -> None:
    executor = _build_executor()
    state = CommercialIntakeState()
    turns = [
        "I'd like a quote for new business coverage",
        "Acme Consulting LLC",
        "Jane Doe",
        "email please",
        "jane@example.com",
        "general liability",
        "We provide small business consulting services.",
    ]

    all_notices: list[str] = []
    for message in turns:
        state, notices = await advance_commercial_intake(state, message, executor, language="en")
        all_notices.append(" ".join(notices))

    assert state.status == CommercialIntakeStatus.REGISTERED
    assert state.lead_reference is not None
    assert _LEAD_REFERENCE_PATTERN.match(state.lead_reference)
    final = all_notices[-1].lower()
    assert "registered" in final
    assert "email" in final


async def test_missing_company_name_blocks_progression() -> None:
    state, notices = await advance_commercial_intake(
        CommercialIntakeState(), "just some random message", _build_executor(), language="en"
    )

    assert state.status == CommercialIntakeStatus.COLLECTING_INFORMATION
    assert state.company_name is None
    assert "company" in " ".join(notices).lower()


async def test_a_message_after_registration_does_not_register_a_second_lead() -> None:
    executor = _build_executor()
    state = CommercialIntakeState()
    for message in [
        "I'd like a quote for new business coverage",
        "Acme Consulting LLC",
        "Jane Doe",
        "email please",
        "jane@example.com",
        "general liability",
        "We provide small business consulting services.",
    ]:
        state, _ = await advance_commercial_intake(state, message, executor, language="en")
    original_reference = state.lead_reference

    state, notices = await advance_commercial_intake(state, "thanks!", executor, language="en")

    assert state.lead_reference == original_reference
    assert state.status == CommercialIntakeStatus.REGISTERED
    assert "already registered" in " ".join(notices).lower()


async def test_lead_registration_tool_failure_is_handled_safely() -> None:
    empty_registry = InMemoryToolRegistry()
    executor = ToolExecutor(tool_registry=empty_registry)
    state = CommercialIntakeState(
        status=CommercialIntakeStatus.READY_TO_REGISTER,
        company_name="Acme Consulting LLC",
        contact_name="Jane Doe",
        preferred_contact_channel="email",
        contact_email="jane@example.com",
        insurance_need="general liability",
        risk_description="A small consulting business.",
    )

    state, notices = await advance_commercial_intake(state, "go ahead", executor, language="en")

    assert state.status == CommercialIntakeStatus.READY_TO_REGISTER
    assert state.lead_reference is None
    assert "unable to register" in " ".join(notices).lower()

"""Unit tests for advance_claims_intake's workflow_provider branch (PBI-06-01): once a caller
confirms, READY_TO_REGISTER must be handled by the injected ClaimsWorkflowProvider instead of
the default in-process _handle_ready_to_register/_handle_registered pair — producing the exact
same notice text/ordering, and forwarding correlation_id/conversation_id/user_id into
ClaimsWorkflowInput (CLAUDE.md §10: correlation ID must be traceable through the workflow)."""

from src.agents.claims.state import ClaimsIntakeState, ClaimsIntakeStatus
from src.agents.claims.workflow import advance_claims_intake
from src.core.workflow_provider.models import ClaimsWorkflowInput, ClaimsWorkflowResult
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry


class _FakeWorkflowProvider:
    def __init__(self, result: ClaimsWorkflowResult) -> None:
        self._result = result
        self.received_input: ClaimsWorkflowInput | None = None

    async def run(self, workflow_input: ClaimsWorkflowInput) -> ClaimsWorkflowResult:
        self.received_input = workflow_input
        return self._result


def _empty_tool_provider() -> ToolExecutor:
    return ToolExecutor(tool_registry=InMemoryToolRegistry())


def _confirmed_state() -> ClaimsIntakeState:
    return ClaimsIntakeState(
        status=ClaimsIntakeStatus.READY_TO_REGISTER,
        policy_number="SYN-POL-0001",
        event_date="2026-08-01",
        event_location="Main St",
        loss_type="collision",
        loss_description="Rear-ended at a stoplight.",
        customer_name="Jane Caller",
        contact_phone="555-123-4567",
        injuries_reported=False,
        third_parties_involved=True,
        confirmed=True,
    )


async def test_successful_workflow_run_produces_registration_and_adjuster_notices() -> None:
    fake_provider = _FakeWorkflowProvider(
        ClaimsWorkflowResult(
            success=True, claim_reference="SYN-CLM-2026-0001", adjuster_name="Synthetic Adjuster A"
        )
    )

    state, notices = await advance_claims_intake(
        _confirmed_state(),
        "",
        _empty_tool_provider(),
        language="en",
        correlation_id="corr-123",
        conversation_id="conv-456",
        user_id="user-789",
        workflow_provider=fake_provider,
    )

    assert state.status == ClaimsIntakeStatus.ADJUSTER_ASSIGNED
    assert state.claim_reference == "SYN-CLM-2026-0001"
    assert state.adjuster_assigned == "Synthetic Adjuster A"
    assert any("SYN-CLM-2026-0001" in notice for notice in notices)
    assert any("Synthetic Adjuster A" in notice for notice in notices)


async def test_workflow_input_carries_correlation_conversation_and_user_id() -> None:
    fake_provider = _FakeWorkflowProvider(
        ClaimsWorkflowResult(success=True, claim_reference="SYN-CLM-2026-0002")
    )

    await advance_claims_intake(
        _confirmed_state(),
        "",
        _empty_tool_provider(),
        language="en",
        correlation_id="corr-123",
        conversation_id="conv-456",
        user_id="user-789",
        workflow_provider=fake_provider,
    )

    assert fake_provider.received_input is not None
    assert fake_provider.received_input.correlation_id == "corr-123"
    assert fake_provider.received_input.conversation_id == "conv-456"
    assert fake_provider.received_input.user_id == "user-789"
    assert fake_provider.received_input.policy_number == "SYN-POL-0001"


async def test_pending_adjuster_leaves_state_registered_not_assigned() -> None:
    fake_provider = _FakeWorkflowProvider(
        ClaimsWorkflowResult(success=True, claim_reference="SYN-CLM-2026-0003", adjuster_name=None)
    )

    state, notices = await advance_claims_intake(
        _confirmed_state(),
        "",
        _empty_tool_provider(),
        language="en",
        workflow_provider=fake_provider,
    )

    assert state.status == ClaimsIntakeStatus.REGISTERED
    assert state.claim_reference == "SYN-CLM-2026-0003"
    assert any("pending" in notice.lower() for notice in notices)


async def test_workflow_failure_keeps_state_ready_to_register_and_reports_failure() -> None:
    fake_provider = _FakeWorkflowProvider(ClaimsWorkflowResult(success=False, error="boom"))

    state, notices = await advance_claims_intake(
        _confirmed_state(),
        "",
        _empty_tool_provider(),
        language="en",
        workflow_provider=fake_provider,
    )

    assert state.status == ClaimsIntakeStatus.READY_TO_REGISTER
    assert state.claim_reference is None
    assert len(notices) == 1


async def test_workflow_provider_none_falls_back_to_default_in_process_handlers() -> None:
    """CLAIMS_WORKFLOW_PROVIDER=inprocess (default, workflow_provider=None) must reach the
    real in-process Tools, never the FakeWorkflowProvider path — proving the two modes are
    genuinely alternative code paths, not always-durable."""
    registry = InMemoryToolRegistry()
    from src.services.tools.adjuster_assignment_tool import AdjusterAssignmentTool
    from src.services.tools.claim_registration_tool import ClaimRegistrationTool

    registry.register(ClaimRegistrationTool())
    registry.register(AdjusterAssignmentTool())
    executor = ToolExecutor(tool_registry=registry)

    state, notices = await advance_claims_intake(
        _confirmed_state(), "", executor, language="en", workflow_provider=None
    )

    assert state.claim_reference is not None
    assert state.claim_reference.startswith("SYN-CLM-")
    assert any("registered" in notice.lower() for notice in notices)

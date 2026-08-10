"""Unit tests for InProcessClaimsWorkflowProvider: runs claim registration then adjuster
assignment through an injected ToolProvider, normalizing every failure mode into
ClaimsWorkflowResult(success=False, ...) — never raising."""

from typing import Any

from src.core.workflow_provider.in_process import InProcessClaimsWorkflowProvider
from src.core.workflow_provider.models import ClaimsWorkflowInput
from src.services.tools.claim_registration_tool import SyntheticClaimRegistrationRecord
from src.services.tools.synthetic.provider import SyntheticAdjusterRecord
from src.tools.models import ToolRequest, ToolResult


class _FakeToolProvider:
    """Records every ToolRequest it receives and returns a scripted ToolResult per tool name."""

    def __init__(self, responses: dict[str, ToolResult[Any]]) -> None:
        self._responses = responses
        self.requests: list[ToolRequest] = []

    async def execute(self, request: ToolRequest) -> ToolResult[Any]:
        self.requests.append(request)
        return self._responses[request.tool_name]


def _workflow_input() -> ClaimsWorkflowInput:
    return ClaimsWorkflowInput(
        correlation_id="corr-1",
        conversation_id="conv-1",
        user_id="user-1",
        policy_number="SYN-POL-0001",
        event_date="2026-08-01",
        event_location="CDMX",
        loss_type="collision",
        loss_description="Fender bender",
        contact_name="Juan Pérez",
        contact_phone="555-0100",
        injuries_reported=False,
        third_parties_involved=False,
    )


async def test_successful_run_returns_claim_reference_and_adjuster_name() -> None:
    tool_provider = _FakeToolProvider(
        {
            "claim_registration": ToolResult(
                tool_name="claim_registration",
                success=True,
                data=SyntheticClaimRegistrationRecord(
                    claim_reference="SYN-CLM-2026-0001", registered_at="2026-08-01T00:00:00Z"
                ),
            ),
            "adjuster_assignment": ToolResult(
                tool_name="adjuster_assignment",
                success=True,
                data=SyntheticAdjusterRecord(
                    adjuster_id="ADJ-1", adjuster_name="Synthetic Adjuster A", region="Central"
                ),
            ),
        }
    )
    provider = InProcessClaimsWorkflowProvider(tool_provider=tool_provider)

    result = await provider.run(_workflow_input())

    assert result.success is True
    assert result.claim_reference == "SYN-CLM-2026-0001"
    assert result.adjuster_name == "Synthetic Adjuster A"
    assert tool_provider.requests[0].tool_name == "claim_registration"
    assert tool_provider.requests[0].correlation_id == "corr-1"
    assert tool_provider.requests[1].tool_name == "adjuster_assignment"
    assert tool_provider.requests[1].tool_input == {"claim_reference": "SYN-CLM-2026-0001"}


async def test_registration_failure_short_circuits_before_adjuster_assignment() -> None:
    tool_provider = _FakeToolProvider(
        {
            "claim_registration": ToolResult(
                tool_name="claim_registration", success=False, error="registration failed"
            ),
        }
    )
    provider = InProcessClaimsWorkflowProvider(tool_provider=tool_provider)

    result = await provider.run(_workflow_input())

    assert result.success is False
    assert result.error == "registration failed"
    assert len(tool_provider.requests) == 1


async def test_adjuster_assignment_failure_still_reports_success_with_pending_adjuster() -> None:
    tool_provider = _FakeToolProvider(
        {
            "claim_registration": ToolResult(
                tool_name="claim_registration",
                success=True,
                data=SyntheticClaimRegistrationRecord(
                    claim_reference="SYN-CLM-2026-0002", registered_at="2026-08-01T00:00:00Z"
                ),
            ),
            "adjuster_assignment": ToolResult(
                tool_name="adjuster_assignment", success=False, error="no adjuster available"
            ),
        }
    )
    provider = InProcessClaimsWorkflowProvider(tool_provider=tool_provider)

    result = await provider.run(_workflow_input())

    assert result.success is True
    assert result.claim_reference == "SYN-CLM-2026-0002"
    assert result.adjuster_name is None

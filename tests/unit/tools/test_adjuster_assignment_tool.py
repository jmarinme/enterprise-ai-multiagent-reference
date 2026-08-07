"""Unit tests for AdjusterAssignmentTool: deterministic (idempotent) assignment per claim
reference, and the missing-reference edge case.
"""

from src.services.tools.adjuster_assignment_tool import AdjusterAssignmentTool
from src.tools.executor import ToolExecutor
from src.tools.models import ToolRequest
from src.tools.registry import InMemoryToolRegistry


def _build_executor() -> ToolExecutor:
    registry = InMemoryToolRegistry()
    registry.register(AdjusterAssignmentTool())
    return ToolExecutor(tool_registry=registry)


async def test_assigns_a_synthetic_adjuster_for_a_valid_claim_reference() -> None:
    result = await _build_executor().execute(
        ToolRequest(
            tool_name="adjuster_assignment", tool_input={"claim_reference": "SYN-CLM-2026-0001"}
        )
    )

    assert result.success is True
    assert result.data is not None
    assert result.data.adjuster_name


async def test_the_same_claim_reference_always_resolves_to_the_same_adjuster() -> None:
    executor = _build_executor()
    request = ToolRequest(
        tool_name="adjuster_assignment", tool_input={"claim_reference": "SYN-CLM-2026-0042"}
    )

    first = await executor.execute(request)
    second = await executor.execute(request)

    assert first.data is not None
    assert second.data is not None
    assert first.data.adjuster_id == second.data.adjuster_id


async def test_fails_gracefully_for_an_empty_claim_reference() -> None:
    result = await _build_executor().execute(
        ToolRequest(tool_name="adjuster_assignment", tool_input={"claim_reference": ""})
    )

    assert result.success is False
    assert result.data is None
    assert result.error is not None

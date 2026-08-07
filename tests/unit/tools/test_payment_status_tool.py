"""Unit tests for PaymentStatusTool: happy path (current and overdue) and not-found path,
run through ToolExecutor. Synthetic data only.
"""

from src.services.tools.payment_status_tool import PaymentStatusTool
from src.tools.executor import ToolExecutor
from src.tools.models import ToolRequest
from src.tools.registry import InMemoryToolRegistry


def _build_executor() -> ToolExecutor:
    registry = InMemoryToolRegistry()
    registry.register(PaymentStatusTool())
    return ToolExecutor(tool_registry=registry)


async def test_returns_payment_current_true_for_a_paid_up_policy() -> None:
    result = await _build_executor().execute(
        ToolRequest(tool_name="payment_status", tool_input={"policy_number": "SYN-POL-0001"})
    )

    assert result.success is True
    assert result.data is not None
    assert result.data.payment_current is True


async def test_returns_payment_current_false_for_an_overdue_policy() -> None:
    result = await _build_executor().execute(
        ToolRequest(tool_name="payment_status", tool_input={"policy_number": "SYN-POL-0002"})
    )

    assert result.success is True
    assert result.data is not None
    assert result.data.payment_current is False


async def test_returns_failure_for_an_unknown_policy() -> None:
    result = await _build_executor().execute(
        ToolRequest(tool_name="payment_status", tool_input={"policy_number": "SYN-POL-9999"})
    )

    assert result.success is False
    assert result.data is None
    assert result.error is not None

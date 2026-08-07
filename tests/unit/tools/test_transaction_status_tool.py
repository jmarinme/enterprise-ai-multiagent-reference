"""Unit tests for TransactionStatusTool: happy path (completed, pending) and not-found path,
run through ToolExecutor. Synthetic data only.
"""

from src.services.tools.transaction_status_tool import TransactionStatusTool
from src.tools.executor import ToolExecutor
from src.tools.models import ToolRequest
from src.tools.registry import InMemoryToolRegistry


def _build_executor() -> ToolExecutor:
    registry = InMemoryToolRegistry()
    registry.register(TransactionStatusTool())
    return ToolExecutor(tool_registry=registry)


async def test_returns_completed_status_for_a_known_transaction() -> None:
    result = await _build_executor().execute(
        ToolRequest(
            tool_name="transaction_status", tool_input={"transaction_reference": "SYN-TXN-0001"}
        )
    )

    assert result.success is True
    assert result.data is not None
    assert result.data.status == "completed"


async def test_returns_pending_status_for_another_known_transaction() -> None:
    result = await _build_executor().execute(
        ToolRequest(
            tool_name="transaction_status", tool_input={"transaction_reference": "SYN-TXN-0002"}
        )
    )

    assert result.success is True
    assert result.data is not None
    assert result.data.status == "pending"


async def test_returns_failure_for_an_unknown_transaction() -> None:
    result = await _build_executor().execute(
        ToolRequest(
            tool_name="transaction_status", tool_input={"transaction_reference": "SYN-TXN-9999"}
        )
    )

    assert result.success is False
    assert result.data is None
    assert result.error is not None

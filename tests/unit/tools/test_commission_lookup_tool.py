"""Unit tests for CommissionLookupTool: available/paid/pending scenarios and the not-found
path, run through ToolExecutor. Synthetic data only.
"""

from src.services.tools.commission_lookup_tool import CommissionLookupTool
from src.tools.executor import ToolExecutor
from src.tools.models import ToolRequest
from src.tools.registry import InMemoryToolRegistry


def _build_executor() -> ToolExecutor:
    registry = InMemoryToolRegistry()
    registry.register(CommissionLookupTool())
    return ToolExecutor(tool_registry=registry)


async def test_returns_available_commission() -> None:
    result = await _build_executor().execute(
        ToolRequest(
            tool_name="commission_lookup",
            tool_input={"broker_id": "SYN-BRK-0001", "commission_period": "2026-Q1"},
        )
    )

    assert result.success is True
    assert result.data is not None
    assert result.data.status == "available"
    assert result.data.amount == 1250.00


async def test_returns_paid_commission() -> None:
    result = await _build_executor().execute(
        ToolRequest(
            tool_name="commission_lookup",
            tool_input={"broker_id": "SYN-BRK-0001", "commission_period": "2026-Q2"},
        )
    )

    assert result.success is True
    assert result.data is not None
    assert result.data.status == "paid"


async def test_returns_pending_commission() -> None:
    result = await _build_executor().execute(
        ToolRequest(
            tool_name="commission_lookup",
            tool_input={"broker_id": "SYN-BRK-0002", "commission_period": "2026-Q1"},
        )
    )

    assert result.success is True
    assert result.data is not None
    assert result.data.status == "pending"


async def test_returns_failure_for_an_unknown_broker_period_combination() -> None:
    result = await _build_executor().execute(
        ToolRequest(
            tool_name="commission_lookup",
            tool_input={"broker_id": "SYN-BRK-0001", "commission_period": "2020-Q1"},
        )
    )

    assert result.success is False
    assert result.data is None
    assert result.error is not None

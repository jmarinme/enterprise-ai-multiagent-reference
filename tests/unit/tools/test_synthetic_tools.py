"""Unit tests for the three synthetic Tools: happy path and not-found path for each,
run directly and through ToolExecutor. Synthetic data only, no Azure, no external APIs.
"""

from src.services.tools.broker_account_lookup_tool import BrokerAccountLookupTool
from src.services.tools.claims_status_tool import ClaimsStatusTool
from src.services.tools.policy_lookup_tool import PolicyLookupTool
from src.tools.executor import ToolExecutor
from src.tools.models import ToolRequest
from src.tools.registry import InMemoryToolRegistry


def _build_executor() -> ToolExecutor:
    registry = InMemoryToolRegistry()
    registry.register(PolicyLookupTool())
    registry.register(ClaimsStatusTool())
    registry.register(BrokerAccountLookupTool())
    return ToolExecutor(tool_registry=registry)


async def test_policy_lookup_tool_returns_known_synthetic_record() -> None:
    executor = _build_executor()

    result = await executor.execute(
        ToolRequest(tool_name="policy_lookup", tool_input={"policy_number": "POL-SYN-0001"})
    )

    assert result.success is True
    assert result.data is not None
    assert result.data.status == "active"
    assert result.data.holder_name == "Synthetic Test Holder A"


async def test_policy_lookup_tool_returns_failure_for_unknown_policy() -> None:
    executor = _build_executor()

    result = await executor.execute(
        ToolRequest(tool_name="policy_lookup", tool_input={"policy_number": "POL-DOES-NOT-EXIST"})
    )

    assert result.success is False
    assert result.data is None
    assert result.error is not None


async def test_claims_status_tool_returns_known_synthetic_record() -> None:
    executor = _build_executor()

    result = await executor.execute(
        ToolRequest(tool_name="claims_status", tool_input={"claim_number": "CLM-SYN-0001"})
    )

    assert result.success is True
    assert result.data is not None
    assert result.data.status == "under_review"


async def test_claims_status_tool_returns_failure_for_unknown_claim() -> None:
    executor = _build_executor()

    result = await executor.execute(
        ToolRequest(tool_name="claims_status", tool_input={"claim_number": "CLM-DOES-NOT-EXIST"})
    )

    assert result.success is False
    assert result.error is not None


async def test_broker_account_lookup_tool_returns_known_synthetic_record() -> None:
    executor = _build_executor()

    result = await executor.execute(
        ToolRequest(tool_name="broker_account_lookup", tool_input={"broker_id": "BRK-SYN-0001"})
    )

    assert result.success is True
    assert result.data is not None
    assert result.data.commission_tier == "gold"


async def test_broker_account_lookup_tool_returns_failure_for_unknown_broker() -> None:
    executor = _build_executor()

    result = await executor.execute(
        ToolRequest(tool_name="broker_account_lookup", tool_input={"broker_id": "BRK-DOES-NOT-EXIST"})
    )

    assert result.success is False
    assert result.error is not None


def test_registry_lists_metadata_for_all_three_synthetic_tools() -> None:
    registry = InMemoryToolRegistry()
    registry.register(PolicyLookupTool())
    registry.register(ClaimsStatusTool())
    registry.register(BrokerAccountLookupTool())

    names = {metadata.name for metadata in registry.list()}

    assert names == {"policy_lookup", "claims_status", "broker_account_lookup"}

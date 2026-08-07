"""Unit tests for CommissionPaymentRequestTool: reference format and sequential uniqueness
within a single tool instance. No financial execution — registration always succeeds and only
records that a payment was requested.
"""

import re

from src.services.tools.commission_payment_request_tool import CommissionPaymentRequestTool
from src.tools.executor import ToolExecutor
from src.tools.models import ToolRequest
from src.tools.registry import InMemoryToolRegistry

_PAYMENT_REQUEST_REFERENCE_PATTERN = re.compile(r"^SYN-PAYREQ-\d{4}-\d{4}$")

_VALID_INPUT = {"broker_id": "SYN-BRK-0001", "commission_period": "2026-Q1"}


def _build_executor() -> ToolExecutor:
    registry = InMemoryToolRegistry()
    registry.register(CommissionPaymentRequestTool())
    return ToolExecutor(tool_registry=registry)


async def test_registration_returns_a_reference_matching_the_expected_format() -> None:
    result = await _build_executor().execute(
        ToolRequest(tool_name="commission_payment_request", tool_input=_VALID_INPUT)
    )

    assert result.success is True
    assert result.data is not None
    assert _PAYMENT_REQUEST_REFERENCE_PATTERN.match(result.data.payment_request_reference)


async def test_sequential_requests_get_distinct_incrementing_references() -> None:
    executor = _build_executor()

    first = await executor.execute(
        ToolRequest(tool_name="commission_payment_request", tool_input=_VALID_INPUT)
    )
    second = await executor.execute(
        ToolRequest(tool_name="commission_payment_request", tool_input=_VALID_INPUT)
    )

    assert first.data is not None
    assert second.data is not None
    assert first.data.payment_request_reference != second.data.payment_request_reference
    assert first.data.payment_request_reference.endswith("0001")
    assert second.data.payment_request_reference.endswith("0002")

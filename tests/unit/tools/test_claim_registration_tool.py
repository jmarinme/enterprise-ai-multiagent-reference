"""Unit tests for ClaimRegistrationTool: reference format and sequential uniqueness within a
single tool instance. No coverage/adjudication logic — registration always succeeds and only
records the reported facts.
"""

import re

from src.services.tools.claim_registration_tool import ClaimRegistrationTool
from src.tools.executor import ToolExecutor
from src.tools.models import ToolRequest
from src.tools.registry import InMemoryToolRegistry

_CLAIM_REFERENCE_PATTERN = re.compile(r"^SYN-CLM-\d{4}-\d{4}$")

_VALID_INPUT = {
    "policy_number": "SYN-POL-0001",
    "event_date": "2026-08-01",
    "event_location": "Main St",
    "loss_type": "collision",
    "loss_description": "Rear-ended at a stoplight.",
    "contact_name": "Jane Caller",
    "contact_phone": "555-123-4567",
}


def _build_executor() -> ToolExecutor:
    registry = InMemoryToolRegistry()
    registry.register(ClaimRegistrationTool())
    return ToolExecutor(tool_registry=registry)


async def test_registration_returns_a_reference_matching_the_expected_format() -> None:
    result = await _build_executor().execute(
        ToolRequest(tool_name="claim_registration", tool_input=_VALID_INPUT)
    )

    assert result.success is True
    assert result.data is not None
    assert _CLAIM_REFERENCE_PATTERN.match(result.data.claim_reference)


async def test_sequential_registrations_get_distinct_incrementing_references() -> None:
    executor = _build_executor()

    first = await executor.execute(
        ToolRequest(tool_name="claim_registration", tool_input=_VALID_INPUT)
    )
    second = await executor.execute(
        ToolRequest(tool_name="claim_registration", tool_input=_VALID_INPUT)
    )

    assert first.data is not None
    assert second.data is not None
    assert first.data.claim_reference != second.data.claim_reference
    assert first.data.claim_reference.endswith("0001")
    assert second.data.claim_reference.endswith("0002")

"""Unit tests for LeadRegistrationTool: reference format and sequential uniqueness within a
single tool instance. No quoting/underwriting logic — registration always succeeds and only
records the reported facts.
"""

import re

from src.services.tools.lead_registration_tool import LeadRegistrationTool
from src.tools.executor import ToolExecutor
from src.tools.models import ToolRequest
from src.tools.registry import InMemoryToolRegistry

_LEAD_REFERENCE_PATTERN = re.compile(r"^SYN-LEAD-\d{4}-\d{4}$")

_VALID_INPUT = {
    "company_name": "Acme Consulting LLC",
    "contact_name": "Jane Doe",
    "preferred_contact_channel": "email",
    "insurance_need": "general liability",
    "risk_description": "A small consulting business.",
    "contact_email": "jane@example.com",
}


def _build_executor() -> ToolExecutor:
    registry = InMemoryToolRegistry()
    registry.register(LeadRegistrationTool())
    return ToolExecutor(tool_registry=registry)


async def test_registration_returns_a_reference_matching_the_expected_format() -> None:
    result = await _build_executor().execute(
        ToolRequest(tool_name="lead_registration", tool_input=_VALID_INPUT)
    )

    assert result.success is True
    assert result.data is not None
    assert _LEAD_REFERENCE_PATTERN.match(result.data.lead_reference)


async def test_sequential_registrations_get_distinct_incrementing_references() -> None:
    executor = _build_executor()

    first = await executor.execute(
        ToolRequest(tool_name="lead_registration", tool_input=_VALID_INPUT)
    )
    second = await executor.execute(
        ToolRequest(tool_name="lead_registration", tool_input=_VALID_INPUT)
    )

    assert first.data is not None
    assert second.data is not None
    assert first.data.lead_reference != second.data.lead_reference
    assert first.data.lead_reference.endswith("0001")
    assert second.data.lead_reference.endswith("0002")

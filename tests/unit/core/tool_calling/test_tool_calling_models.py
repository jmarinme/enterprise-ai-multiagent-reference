"""Unit tests for the Tool Calling orchestration framework's typed contracts (PBI-02-04):
construction, defaults, camelCase serialization for the API-facing ToolCallResult, and
ToolCallingContext's max_iterations validation.
"""

import pytest
from pydantic import ValidationError

from src.core.tool_calling.models import (
    DEFAULT_MAX_TOOL_CALL_ITERATIONS,
    ToolCallingContext,
    ToolCallingResponse,
    ToolCallResult,
)


def test_tool_call_result_carries_success_data_and_no_error() -> None:
    result = ToolCallResult(
        call_id="call-1", tool_name="policy_lookup", success=True, data={"status": "active"}
    )

    assert result.success is True
    assert result.data == {"status": "active"}
    assert result.error is None
    assert result.error_type is None


def test_tool_call_result_carries_error_and_error_type_on_failure() -> None:
    result = ToolCallResult(
        call_id="call-1",
        tool_name="policy_lookup",
        success=False,
        error="not authorized",
        error_type="unauthorized",
    )

    assert result.success is False
    assert result.data is None
    assert result.error == "not authorized"
    assert result.error_type == "unauthorized"


def test_tool_call_result_serializes_with_camel_case_field_names() -> None:
    result = ToolCallResult(call_id="call-1", tool_name="policy_lookup", success=True)

    dumped = result.model_dump(by_alias=True)

    assert dumped["callId"] == "call-1"
    assert dumped["toolName"] == "policy_lookup"
    assert dumped["errorType"] is None


def test_tool_calling_context_defaults_max_iterations_to_the_conservative_constant() -> None:
    context = ToolCallingContext(agent_name="ClaimsAgent", allowed_tools=["policy_lookup"])

    assert context.max_iterations == DEFAULT_MAX_TOOL_CALL_ITERATIONS


def test_tool_calling_context_defaults_allowed_tools_to_empty() -> None:
    context = ToolCallingContext(agent_name="ClaimsAgent")

    assert context.allowed_tools == []


@pytest.mark.parametrize("max_iterations", [0, -1])
def test_tool_calling_context_rejects_a_non_positive_max_iterations(max_iterations: int) -> None:
    with pytest.raises(ValidationError):
        ToolCallingContext(
            agent_name="ClaimsAgent", allowed_tools=["policy_lookup"], max_iterations=max_iterations
        )


def test_tool_calling_response_defaults_tool_calls_to_empty_and_not_stopped() -> None:
    response = ToolCallingResponse(text="final answer", iterations=1)

    assert response.tool_calls == []
    assert response.stopped_due_to_max_iterations is False

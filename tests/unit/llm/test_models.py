"""Unit tests for LLM request/response contracts and generation settings validation."""

import pytest
from pydantic import ValidationError

from src.llm.models import (
    LLMGenerationSettings,
    LLMMessage,
    LLMMessageRole,
    LLMRequest,
    LLMResponse,
    LLMToolDefinition,
    LLMUsage,
    ToolCallArgument,
    ToolCallRequest,
)


def test_generation_settings_defaults_are_deterministic_friendly() -> None:
    settings = LLMGenerationSettings()

    assert settings.temperature == 0.0
    assert settings.max_output_tokens == 512
    assert settings.timeout_seconds == 30.0
    assert settings.model is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"temperature": -0.1},
        {"temperature": 2.1},
        {"max_output_tokens": 0},
        {"max_output_tokens": -1},
        {"timeout_seconds": 0},
        {"timeout_seconds": -5},
    ],
)
def test_generation_settings_rejects_out_of_range_values(kwargs: dict) -> None:
    with pytest.raises(ValidationError):
        LLMGenerationSettings(**kwargs)


def test_generation_settings_accepts_boundary_values() -> None:
    settings = LLMGenerationSettings(temperature=0.0, max_output_tokens=1, timeout_seconds=0.01)

    assert settings.temperature == 0.0
    assert settings.max_output_tokens == 1


def test_llm_request_carries_messages_and_context_identifiers() -> None:
    request = LLMRequest(
        messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")],
        correlation_id="corr-1",
        conversation_id="conv-1",
        user_id="user-1",
    )

    assert len(request.messages) == 1
    assert request.settings == LLMGenerationSettings()
    assert request.correlation_id == "corr-1"


def test_llm_response_defaults_usage_to_zero() -> None:
    response = LLMResponse(text="hello", model="mock-llm")

    assert response.usage == LLMUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)


def test_llm_request_defaults_tools_to_empty() -> None:
    request = LLMRequest(messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")])

    assert request.tools == []


def test_llm_response_defaults_tool_calls_to_empty() -> None:
    response = LLMResponse(text="hello", model="mock-llm")

    assert response.tool_calls == []


def test_llm_message_defaults_tool_call_id_to_none() -> None:
    message = LLMMessage(role=LLMMessageRole.USER, content="hello")

    assert message.tool_call_id is None


def test_llm_message_supports_tool_role_with_a_call_id() -> None:
    message = LLMMessage(role=LLMMessageRole.TOOL, content='{"success": true}', tool_call_id="call_1")

    assert message.role == LLMMessageRole.TOOL
    assert message.tool_call_id == "call_1"


def test_llm_tool_definition_carries_name_description_and_parameters_schema() -> None:
    definition = LLMToolDefinition(
        name="policy_lookup",
        description="Looks up a policy",
        parameters_schema={"type": "object", "properties": {"policy_number": {"type": "string"}}},
    )

    assert definition.name == "policy_lookup"
    assert definition.parameters_schema["type"] == "object"


def test_llm_tool_definition_defaults_parameters_schema_to_empty() -> None:
    definition = LLMToolDefinition(name="policy_lookup", description="Looks up a policy")

    assert definition.parameters_schema == {}


def test_tool_call_request_carries_call_id_tool_name_and_arguments() -> None:
    request = ToolCallRequest(
        call_id="call_1",
        tool_name="policy_lookup",
        arguments=[ToolCallArgument(name="policy_number", value="SYN-POL-0001")],
    )

    assert request.call_id == "call_1"
    assert request.tool_name == "policy_lookup"
    assert request.arguments[0].name == "policy_number"
    assert request.arguments[0].value == "SYN-POL-0001"


def test_tool_call_request_defaults_arguments_to_empty() -> None:
    request = ToolCallRequest(call_id="call_1", tool_name="policy_lookup")

    assert request.arguments == []

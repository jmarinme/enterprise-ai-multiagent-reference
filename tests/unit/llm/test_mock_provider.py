"""Unit tests for MockLLMProvider: deterministic, no Azure connectivity, typed LLMResponse."""

from src.llm.mock_provider import MockLLMProvider
from src.llm.models import (
    LLMMessage,
    LLMMessageRole,
    LLMRequest,
    LLMToolDefinition,
    ToolCallArgument,
    ToolCallRequest,
)


async def test_generate_is_deterministic_for_the_same_request() -> None:
    provider = MockLLMProvider()
    request = LLMRequest(messages=[LLMMessage(role=LLMMessageRole.USER, content="hello there")])

    first = await provider.generate(request)
    second = await provider.generate(request)

    assert first.text == second.text
    assert first.usage == second.usage


async def test_generate_returns_a_typed_llm_response() -> None:
    provider = MockLLMProvider()
    request = LLMRequest(
        messages=[
            LLMMessage(role=LLMMessageRole.SYSTEM, content="system framing"),
            LLMMessage(role=LLMMessageRole.USER, content="a user question"),
        ],
        correlation_id="corr-1",
    )

    response = await provider.generate(request)

    assert isinstance(response.text, str) and response.text
    assert response.model == "mock-llm"
    assert response.correlation_id == "corr-1"
    assert response.usage.total_tokens == response.usage.prompt_tokens + response.usage.completion_tokens


async def test_generate_output_varies_with_last_user_message_length() -> None:
    provider = MockLLMProvider()
    short_request = LLMRequest(messages=[LLMMessage(role=LLMMessageRole.USER, content="hi")])
    long_request = LLMRequest(
        messages=[LLMMessage(role=LLMMessageRole.USER, content="a much longer message here")]
    )

    short_response = await provider.generate(short_request)
    long_response = await provider.generate(long_request)

    assert short_response.text != long_response.text


async def test_generate_with_no_user_message_still_succeeds() -> None:
    provider = MockLLMProvider()
    request = LLMRequest(messages=[LLMMessage(role=LLMMessageRole.SYSTEM, content="system only")])

    response = await provider.generate(request)

    assert response.text


def _policy_lookup_call() -> ToolCallRequest:
    return ToolCallRequest(
        call_id="call-1",
        tool_name="policy_lookup",
        arguments=[ToolCallArgument(name="policy_number", value="SYN-POL-0001")],
    )


async def test_default_mock_provider_never_requests_a_tool_call() -> None:
    """Zero-arg construction (used by every pre-PBI-02-04 caller) must behave byte-identically
    to before this PBI — no tool_call_plan means no tool_calls, ever, regardless of what tools
    are offered."""
    provider = MockLLMProvider()
    request = LLMRequest(
        messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")],
        tools=[LLMToolDefinition(name="policy_lookup", description="Looks up a policy")],
    )

    response = await provider.generate(request)

    assert response.tool_calls == []
    assert response.text


async def test_scripted_provider_requests_only_the_offered_tool_calls() -> None:
    provider = MockLLMProvider(tool_call_plan=[_policy_lookup_call()])
    request = LLMRequest(
        messages=[LLMMessage(role=LLMMessageRole.USER, content="check my policy")],
        tools=[LLMToolDefinition(name="policy_lookup", description="Looks up a policy")],
    )

    response = await provider.generate(request)

    assert response.tool_calls == [_policy_lookup_call()]
    assert response.text == ""


async def test_scripted_provider_filters_out_calls_for_tools_not_offered() -> None:
    """A scripted plan naming a tool the caller did not offer this turn must never be
    returned — MockLLMProvider only ever requests tools genuinely present in request.tools."""
    provider = MockLLMProvider(tool_call_plan=[_policy_lookup_call()])
    request = LLMRequest(
        messages=[LLMMessage(role=LLMMessageRole.USER, content="check my policy")],
        tools=[LLMToolDefinition(name="payment_status", description="Looks up payment status")],
    )

    response = await provider.generate(request)

    assert response.tool_calls == []


async def test_scripted_provider_does_not_request_a_tool_call_without_tool_definitions() -> None:
    provider = MockLLMProvider(tool_call_plan=[_policy_lookup_call()])
    request = LLMRequest(messages=[LLMMessage(role=LLMMessageRole.USER, content="check my policy")])

    response = await provider.generate(request)

    assert response.tool_calls == []


async def test_scripted_provider_stops_requesting_once_a_tool_result_message_exists() -> None:
    """Once a TOOL-role message is already in history (the result of a prior request),
    MockLLMProvider gives its normal deterministic text response instead of looping forever —
    this is what makes MockLLMProvider itself incapable of an infinite loop."""
    provider = MockLLMProvider(tool_call_plan=[_policy_lookup_call()])
    request = LLMRequest(
        messages=[
            LLMMessage(role=LLMMessageRole.USER, content="check my policy"),
            LLMMessage(
                role=LLMMessageRole.TOOL,
                content='{"success": true}',
                tool_call_id="call-1",
            ),
        ],
        tools=[LLMToolDefinition(name="policy_lookup", description="Looks up a policy")],
    )

    response = await provider.generate(request)

    assert response.tool_calls == []
    assert response.text

"""Unit tests for MockLLMProvider: deterministic, no Azure connectivity, typed LLMResponse."""

from src.llm.mock_provider import MockLLMProvider
from src.llm.models import LLMMessage, LLMMessageRole, LLMRequest


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

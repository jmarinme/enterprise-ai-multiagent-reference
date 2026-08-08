"""Unit tests for OllamaLLMProvider, fully mocked — no real Ollama server calls anywhere.

Covers: configuration validation, mocked success, mocked timeout, mocked connection/rate-limit/
generic HTTP errors, and Tool Calling mapping (request.tools -> Ollama's tools=, response
tool_calls -> typed ToolCallRequest, including the synthesized call_id and already-parsed-dict
arguments that distinguish Ollama's shape from AzureOpenAIProvider's).
"""

from __future__ import annotations

from typing import Any, Self
from unittest.mock import MagicMock, patch

import aiohttp
import pytest

from src.llm.exceptions import (
    LLMConfigurationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from src.llm.models import (
    LLMMessage,
    LLMMessageRole,
    LLMRequest,
    LLMToolDefinition,
    ToolCallArgument,
    ToolCallRequest,
)
from src.llm.ollama_provider import OllamaLLMProvider


class _FakePostContextManager:
    """Stands in for aiohttp's `async with session.post(...) as response:` request context
    manager. Raises exception (if given) on __aenter__, matching real aiohttp's behavior of
    raising connection/timeout errors when the request is actually sent."""

    def __init__(
        self, *, json_data: dict[str, Any] | None = None, exception: Exception | None = None,
        status: int = 200,
    ) -> None:
        self._json_data = json_data
        self._exception = exception
        self.status = status
        self.request_url: str | None = None
        self.request_json: dict[str, Any] | None = None

    async def __aenter__(self) -> Self:
        if self._exception is not None:
            raise self._exception
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise aiohttp.ClientResponseError(
                request_info=MagicMock(), history=(), status=self.status, message="error"
            )

    async def json(self) -> dict[str, Any]:
        return self._json_data or {}


class _FakeSession:
    def __init__(self, post_context_manager: _FakePostContextManager) -> None:
        self._post_context_manager = post_context_manager

    def post(self, url: str, json: dict[str, Any] | None = None) -> _FakePostContextManager:
        self._post_context_manager.request_url = url
        self._post_context_manager.request_json = json
        return self._post_context_manager

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


def _patch_session(post_context_manager: _FakePostContextManager) -> Any:
    return patch("aiohttp.ClientSession", return_value=_FakeSession(post_context_manager))


def _build_provider() -> OllamaLLMProvider:
    return OllamaLLMProvider(base_url="http://localhost:11434", model="llama3.1")


def test_missing_base_url_raises_configuration_error() -> None:
    with pytest.raises(LLMConfigurationError):
        OllamaLLMProvider(base_url="", model="llama3.1")


def test_missing_model_raises_configuration_error() -> None:
    with pytest.raises(LLMConfigurationError):
        OllamaLLMProvider(base_url="http://localhost:11434", model="")


async def test_generate_success_returns_typed_llm_response() -> None:
    fake_response = _FakePostContextManager(
        json_data={
            "model": "llama3.1",
            "message": {"role": "assistant", "content": "hello back"},
            "prompt_eval_count": 10,
            "eval_count": 5,
        }
    )
    provider = _build_provider()

    with _patch_session(fake_response):
        response = await provider.generate(
            LLMRequest(messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")])
        )

    assert response.text == "hello back"
    assert response.model == "llama3.1"
    assert response.usage.prompt_tokens == 10
    assert response.usage.completion_tokens == 5
    assert response.usage.total_tokens == 15
    assert response.tool_calls == []


async def test_generate_posts_to_the_configured_base_url_and_model() -> None:
    fake_response = _FakePostContextManager(
        json_data={"model": "llama3.1", "message": {"content": "ok"}}
    )
    provider = OllamaLLMProvider(base_url="http://localhost:11434/", model="llama3.1")

    with _patch_session(fake_response):
        await provider.generate(
            LLMRequest(messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")])
        )

    assert fake_response.request_url == "http://localhost:11434/api/chat"
    assert fake_response.request_json is not None
    assert fake_response.request_json["model"] == "llama3.1"
    assert fake_response.request_json["stream"] is False


async def test_generate_timeout_raises_llm_timeout_error() -> None:
    fake_response = _FakePostContextManager(exception=TimeoutError())
    provider = _build_provider()

    with _patch_session(fake_response), pytest.raises(LLMTimeoutError):
        await provider.generate(
            LLMRequest(messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")])
        )


async def test_generate_connection_error_raises_llm_provider_error() -> None:
    fake_response = _FakePostContextManager(
        exception=aiohttp.ClientConnectionError("connection refused")
    )
    provider = _build_provider()

    with _patch_session(fake_response), pytest.raises(LLMProviderError):
        await provider.generate(
            LLMRequest(messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")])
        )


async def test_generate_rate_limited_response_raises_llm_rate_limit_error() -> None:
    fake_response = _FakePostContextManager(status=429)
    provider = _build_provider()

    with _patch_session(fake_response), pytest.raises(LLMRateLimitError):
        await provider.generate(
            LLMRequest(messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")])
        )


async def test_generate_generic_http_error_raises_llm_provider_error() -> None:
    fake_response = _FakePostContextManager(status=500)
    provider = _build_provider()

    with _patch_session(fake_response), pytest.raises(LLMProviderError):
        await provider.generate(
            LLMRequest(messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")])
        )


async def test_generate_generic_client_error_raises_llm_provider_error() -> None:
    fake_response = _FakePostContextManager(
        exception=aiohttp.ClientPayloadError("malformed payload")
    )
    provider = _build_provider()

    with _patch_session(fake_response), pytest.raises(LLMProviderError):
        await provider.generate(
            LLMRequest(messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")])
        )


async def test_generate_with_tools_passes_tool_definitions_to_ollama() -> None:
    fake_response = _FakePostContextManager(
        json_data={"model": "llama3.1", "message": {"content": "ok"}}
    )
    provider = _build_provider()

    with _patch_session(fake_response):
        await provider.generate(
            LLMRequest(
                messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")],
                tools=[
                    LLMToolDefinition(
                        name="policy_lookup",
                        description="Looks up a policy",
                        parameters_schema={"type": "object", "properties": {"policy_number": {}}},
                    )
                ],
            )
        )

    assert fake_response.request_json is not None
    assert fake_response.request_json["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "policy_lookup",
                "description": "Looks up a policy",
                "parameters": {"type": "object", "properties": {"policy_number": {}}},
            },
        }
    ]


async def test_generate_without_tools_omits_the_tools_field() -> None:
    fake_response = _FakePostContextManager(
        json_data={"model": "llama3.1", "message": {"content": "ok"}}
    )
    provider = _build_provider()

    with _patch_session(fake_response):
        await provider.generate(
            LLMRequest(messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")])
        )

    assert fake_response.request_json is not None
    assert "tools" not in fake_response.request_json


async def test_generate_maps_response_tool_calls_with_synthesized_ids_and_dict_arguments() -> (
    None
):
    """Unlike OpenAI, Ollama's tool_calls carry no id and arguments arrive as an already-parsed
    dict, not a JSON string — this test proves both differences are handled correctly."""
    fake_response = _FakePostContextManager(
        json_data={
            "model": "llama3.1",
            "message": {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "policy_lookup",
                            "arguments": {"policy_number": "SYN-POL-0001"},
                        }
                    }
                ],
            },
        }
    )
    provider = _build_provider()

    with _patch_session(fake_response):
        response = await provider.generate(
            LLMRequest(
                messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")],
                tools=[LLMToolDefinition(name="policy_lookup", description="Looks up a policy")],
            )
        )

    assert len(response.tool_calls) == 1
    call = response.tool_calls[0]
    assert call.call_id == "ollama-call-0"
    assert call.tool_name == "policy_lookup"
    assert {arg.name: arg.value for arg in call.arguments} == {"policy_number": "SYN-POL-0001"}


async def test_generate_maps_a_tool_role_message_to_the_ollama_shape() -> None:
    fake_response = _FakePostContextManager(
        json_data={"model": "llama3.1", "message": {"content": "ok"}}
    )
    provider = _build_provider()

    with _patch_session(fake_response):
        await provider.generate(
            LLMRequest(
                messages=[
                    LLMMessage(role=LLMMessageRole.USER, content="hello"),
                    LLMMessage(
                        role=LLMMessageRole.TOOL,
                        content='{"success": true}',
                        tool_call_id="call-1",
                    ),
                ]
            )
        )


async def test_generate_maps_an_assistant_tool_calls_message_to_the_ollama_shape() -> None:
    """PBI-04-03: mirrors AzureOpenAIProvider's own fix — an ASSISTANT message carrying
    tool_calls must be forwarded to Ollama too, in its own documented shape (no id, arguments
    as a plain object), so the same protocol-compliant history the orchestrator now always
    builds is honored by every provider, not special-cased to Azure OpenAI."""
    fake_response = _FakePostContextManager(
        json_data={"model": "llama3.1", "message": {"content": "ok"}}
    )
    provider = _build_provider()

    with _patch_session(fake_response):
        await provider.generate(
            LLMRequest(
                messages=[
                    LLMMessage(role=LLMMessageRole.USER, content="hello"),
                    LLMMessage(
                        role=LLMMessageRole.ASSISTANT,
                        content="",
                        tool_calls=[
                            ToolCallRequest(
                                call_id="call-1",
                                tool_name="policy_lookup",
                                arguments=[
                                    ToolCallArgument(name="policy_number", value="SYN-POL-0001")
                                ],
                            )
                        ],
                    ),
                    LLMMessage(
                        role=LLMMessageRole.TOOL,
                        content='{"success": true}',
                        tool_call_id="call-1",
                    ),
                ]
            )
        )

    sent_messages = fake_response.request_json["messages"]
    assert sent_messages[1] == {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {"function": {"name": "policy_lookup", "arguments": {"policy_number": "SYN-POL-0001"}}}
        ],
    }

    assert fake_response.request_json is not None
    assert fake_response.request_json["messages"][-1] == {
        "role": "tool",
        "content": '{"success": true}',
        "tool_call_id": "call-1",
    }

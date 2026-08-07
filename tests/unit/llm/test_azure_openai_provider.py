"""Unit tests for AzureOpenAIProvider, fully mocked — no real Azure/OpenAI calls anywhere.

Covers: configuration validation, mocked success, mocked timeout, mocked rate limit, mocked
generic provider error, and the Entra ID vs. SecretProvider-backed API-key auth paths.
"""

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError

from src.llm.exceptions import (
    LLMConfigurationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from src.llm.models import LLMMessage, LLMMessageRole, LLMRequest, LLMToolDefinition

if TYPE_CHECKING:
    from src.llm.azure_openai_provider import AzureOpenAIProvider


def _fake_request() -> httpx.Request:
    return httpx.Request("POST", "https://example.openai.azure.com/chat/completions")


def _fake_response(status_code: int) -> httpx.Response:
    return httpx.Response(status_code=status_code, request=_fake_request())


def test_missing_endpoint_raises_configuration_error() -> None:
    from src.llm.azure_openai_provider import AzureOpenAIProvider

    with pytest.raises(LLMConfigurationError):
        AzureOpenAIProvider(endpoint="", deployment="gpt-4o-mini", api_version="2024-10-21")


def test_missing_deployment_raises_configuration_error() -> None:
    from src.llm.azure_openai_provider import AzureOpenAIProvider

    with pytest.raises(LLMConfigurationError):
        AzureOpenAIProvider(
            endpoint="https://example.openai.azure.com/", deployment="", api_version="2024-10-21"
        )


def _build_provider() -> "AzureOpenAIProvider":
    from src.llm.azure_openai_provider import AzureOpenAIProvider

    return AzureOpenAIProvider(
        endpoint="https://example.openai.azure.com/",
        deployment="gpt-4o-mini",
        api_version="2024-10-21",
    )


def _fake_completion(
    text: str = "a mocked completion", tool_calls: list[SimpleNamespace] | None = None
) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content=text, tool_calls=tool_calls))
        ],
        model="gpt-4o-mini",
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


@patch("src.llm.azure_openai_provider.AsyncAzureOpenAI")
@patch("azure.identity.aio.DefaultAzureCredential")
@patch("azure.identity.aio.get_bearer_token_provider")
async def test_generate_success_returns_typed_llm_response(
    mock_token_provider: MagicMock, mock_credential_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    mock_client = mock_client_cls.return_value
    mock_client.chat.completions.create = AsyncMock(return_value=_fake_completion("hello back"))
    provider = _build_provider()

    response = await provider.generate(
        LLMRequest(messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")])
    )

    assert response.text == "hello back"
    assert response.model == "gpt-4o-mini"
    assert response.usage.total_tokens == 15


@patch("src.llm.azure_openai_provider.AsyncAzureOpenAI")
@patch("azure.identity.aio.DefaultAzureCredential")
@patch("azure.identity.aio.get_bearer_token_provider")
async def test_generate_timeout_raises_llm_timeout_error(
    mock_token_provider: MagicMock, mock_credential_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    mock_client = mock_client_cls.return_value
    mock_client.chat.completions.create = AsyncMock(
        side_effect=APITimeoutError(request=_fake_request())
    )
    provider = _build_provider()

    with pytest.raises(LLMTimeoutError):
        await provider.generate(
            LLMRequest(messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")])
        )


@patch("src.llm.azure_openai_provider.AsyncAzureOpenAI")
@patch("azure.identity.aio.DefaultAzureCredential")
@patch("azure.identity.aio.get_bearer_token_provider")
async def test_generate_rate_limit_raises_llm_rate_limit_error(
    mock_token_provider: MagicMock, mock_credential_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    mock_client = mock_client_cls.return_value
    mock_client.chat.completions.create = AsyncMock(
        side_effect=RateLimitError(
            "rate limited", response=_fake_response(429), body=None
        )
    )
    provider = _build_provider()

    with pytest.raises(LLMRateLimitError):
        await provider.generate(
            LLMRequest(messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")])
        )


@patch("src.llm.azure_openai_provider.AsyncAzureOpenAI")
@patch("azure.identity.aio.DefaultAzureCredential")
@patch("azure.identity.aio.get_bearer_token_provider")
async def test_generate_connection_error_raises_llm_provider_error(
    mock_token_provider: MagicMock, mock_credential_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    mock_client = mock_client_cls.return_value
    mock_client.chat.completions.create = AsyncMock(
        side_effect=APIConnectionError(request=_fake_request())
    )
    provider = _build_provider()

    with pytest.raises(LLMProviderError):
        await provider.generate(
            LLMRequest(messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")])
        )


@patch("src.llm.azure_openai_provider.AsyncAzureOpenAI")
@patch("azure.identity.aio.DefaultAzureCredential")
@patch("azure.identity.aio.get_bearer_token_provider")
async def test_generate_generic_status_error_raises_llm_provider_error(
    mock_token_provider: MagicMock, mock_credential_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    mock_client = mock_client_cls.return_value
    mock_client.chat.completions.create = AsyncMock(
        side_effect=APIStatusError(
            "internal server error", response=_fake_response(500), body=None
        )
    )
    provider = _build_provider()

    with pytest.raises(LLMProviderError):
        await provider.generate(
            LLMRequest(messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")])
        )


@patch("src.llm.azure_openai_provider.AsyncAzureOpenAI")
@patch("azure.identity.aio.DefaultAzureCredential")
@patch("azure.identity.aio.get_bearer_token_provider")
async def test_default_auth_uses_entra_id_not_secret_provider(
    mock_token_provider: MagicMock, mock_credential_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    provider = _build_provider()
    mock_client_cls.return_value.chat.completions.create = AsyncMock(
        return_value=_fake_completion()
    )

    await provider.generate(
        LLMRequest(messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")])
    )

    mock_credential_cls.assert_called_once()
    _, client_kwargs = mock_client_cls.call_args
    assert "azure_ad_token_provider" in client_kwargs
    assert "api_key" not in client_kwargs


@patch("src.llm.azure_openai_provider.AsyncAzureOpenAI")
async def test_api_key_auth_uses_secret_provider_not_environment(
    mock_client_cls: MagicMock,
) -> None:
    from src.llm.azure_openai_provider import AzureOpenAIProvider

    class _StubSecretProvider:
        async def get_secret(self, secret_name: str) -> str:
            assert secret_name == "azure-openai-api-key"
            return "mock-secret-value-not-a-real-key"

    mock_client_cls.return_value.chat.completions.create = AsyncMock(
        return_value=_fake_completion()
    )
    provider = AzureOpenAIProvider(
        endpoint="https://example.openai.azure.com/",
        deployment="gpt-4o-mini",
        api_version="2024-10-21",
        secret_provider=_StubSecretProvider(),
        api_key_secret_name="azure-openai-api-key",
    )

    await provider.generate(
        LLMRequest(messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")])
    )

    _, client_kwargs = mock_client_cls.call_args
    assert client_kwargs.get("api_key") == "mock-secret-value-not-a-real-key"
    assert "azure_ad_token_provider" not in client_kwargs


def _fake_function_tool_call(
    call_id: str, name: str, arguments_json: str
) -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments_json),
    )


@patch("src.llm.azure_openai_provider.AsyncAzureOpenAI")
@patch("azure.identity.aio.DefaultAzureCredential")
@patch("azure.identity.aio.get_bearer_token_provider")
async def test_generate_with_tools_passes_tool_definitions_to_the_sdk(
    mock_token_provider: MagicMock, mock_credential_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    mock_client = mock_client_cls.return_value
    mock_client.chat.completions.create = AsyncMock(return_value=_fake_completion())
    provider = _build_provider()

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

    _, call_kwargs = mock_client.chat.completions.create.call_args
    assert call_kwargs["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "policy_lookup",
                "description": "Looks up a policy",
                "parameters": {"type": "object", "properties": {"policy_number": {}}},
            },
        }
    ]


@patch("src.llm.azure_openai_provider.AsyncAzureOpenAI")
@patch("azure.identity.aio.DefaultAzureCredential")
@patch("azure.identity.aio.get_bearer_token_provider")
async def test_generate_maps_response_tool_calls_to_typed_tool_call_requests(
    mock_token_provider: MagicMock, mock_credential_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    mock_client = mock_client_cls.return_value
    mock_client.chat.completions.create = AsyncMock(
        return_value=_fake_completion(
            text="",
            tool_calls=[
                _fake_function_tool_call(
                    "call_1", "policy_lookup", '{"policy_number": "SYN-POL-0001"}'
                )
            ],
        )
    )
    provider = _build_provider()

    response = await provider.generate(
        LLMRequest(
            messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")],
            tools=[
                LLMToolDefinition(name="policy_lookup", description="Looks up a policy")
            ],
        )
    )

    assert len(response.tool_calls) == 1
    call = response.tool_calls[0]
    assert call.call_id == "call_1"
    assert call.tool_name == "policy_lookup"
    assert {arg.name: arg.value for arg in call.arguments} == {"policy_number": "SYN-POL-0001"}


@patch("src.llm.azure_openai_provider.AsyncAzureOpenAI")
@patch("azure.identity.aio.DefaultAzureCredential")
@patch("azure.identity.aio.get_bearer_token_provider")
async def test_generate_raises_llm_provider_error_for_malformed_tool_call_arguments(
    mock_token_provider: MagicMock, mock_credential_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    mock_client = mock_client_cls.return_value
    mock_client.chat.completions.create = AsyncMock(
        return_value=_fake_completion(
            text="",
            tool_calls=[_fake_function_tool_call("call_1", "policy_lookup", "not-json")],
        )
    )
    provider = _build_provider()

    with pytest.raises(LLMProviderError):
        await provider.generate(
            LLMRequest(
                messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")],
                tools=[LLMToolDefinition(name="policy_lookup", description="Looks up a policy")],
            )
        )


@patch("src.llm.azure_openai_provider.AsyncAzureOpenAI")
@patch("azure.identity.aio.DefaultAzureCredential")
@patch("azure.identity.aio.get_bearer_token_provider")
async def test_generate_maps_a_tool_role_message_to_the_sdk_tool_message_shape(
    mock_token_provider: MagicMock, mock_credential_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    mock_client = mock_client_cls.return_value
    mock_client.chat.completions.create = AsyncMock(return_value=_fake_completion())
    provider = _build_provider()

    await provider.generate(
        LLMRequest(
            messages=[
                LLMMessage(role=LLMMessageRole.USER, content="hello"),
                LLMMessage(
                    role=LLMMessageRole.TOOL,
                    content='{"success": true}',
                    tool_call_id="call_1",
                ),
            ]
        )
    )

    _, call_kwargs = mock_client.chat.completions.create.call_args
    assert call_kwargs["messages"][-1] == {
        "role": "tool",
        "content": '{"success": true}',
        "tool_call_id": "call_1",
    }

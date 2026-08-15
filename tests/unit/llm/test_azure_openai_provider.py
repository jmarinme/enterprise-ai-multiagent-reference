"""Unit tests for AzureOpenAIProvider, fully mocked — no real Azure/OpenAI calls anywhere.

Covers: configuration validation, mocked success, mocked timeout, mocked rate limit, mocked
generic provider error, and the Entra ID vs. SecretProvider-backed API-key auth paths.
"""

import logging
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
from src.llm.models import (
    LLMGenerationSettings,
    LLMMessage,
    LLMMessageRole,
    LLMRequest,
    LLMResponseSchema,
    LLMToolDefinition,
    ToolCallArgument,
    ToolCallRequest,
)

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


def _build_provider(
    deployment: str = "gpt-4o-mini", model_name: str | None = None
) -> "AzureOpenAIProvider":
    from src.llm.azure_openai_provider import AzureOpenAIProvider

    return AzureOpenAIProvider(
        endpoint="https://example.openai.azure.com/",
        deployment=deployment,
        api_version="2024-10-21",
        model_name=model_name,
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
async def test_generate_status_error_logs_sanitized_provider_diagnostic(
    mock_token_provider: MagicMock,
    mock_credential_cls: MagicMock,
    mock_client_cls: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """PBI-14-13: the real Azure OpenAI error detail (status/code/type/param/message/deployment/
    api_version) must reach the logs so a live DEV 400 is diagnosable — sanitized, never
    leaking secrets/tokens/Authorization headers/raw prompts/raw user messages/raw request or
    response bodies. Body shape and message text are copied verbatim from a real, live DEV
    reproduction (PBI-14-13, correlationId ce901473-5337-4e28-acad-8b853ccca2b4): Azure's SDK
    exposes APIStatusError.body FLAT (message/type/param/code as top-level keys), not wrapped
    in an {"error": {...}} envelope as OpenAI's own docs show — an earlier version of this
    diagnostic assumed the wrapped shape and silently logged None for every field against this
    exact real response."""
    mock_client = mock_client_cls.return_value
    mock_client.chat.completions.create = AsyncMock(
        side_effect=APIStatusError(
            "Bad Request",
            response=_fake_response(400),
            body={
                "message": (
                    "Invalid schema for response_format 'turn_interpretation': In "
                    "context=(), 'required' is required to be supplied and to be an array "
                    "including every key in properties. Extra required key 'corrections' "
                    "supplied."
                ),
                "type": "invalid_request_error",
                "param": "response_format",
                "code": None,
            },
        )
    )
    provider = _build_provider(deployment="chat")

    with (
        caplog.at_level(logging.ERROR, logger="src.llm.azure_openai_provider"),
        pytest.raises(LLMProviderError),
    ):
        await provider.generate(
            LLMRequest(
                messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")],
                response_schema=LLMResponseSchema(
                    name="turn_interpretation", schema={"type": "object"}
                ),
            )
        )

    logged = " ".join(record.getMessage() for record in caplog.records)
    assert "http_status=400" in logged
    assert "invalid_request_error" in logged
    assert "response_format" in logged  # provider_error_param
    assert "corrections" in logged  # the real, actionable schema-validation detail
    assert "deployment=chat" in logged
    assert "api_version=2024-10-21" in logged
    # Never a secret/token/header, regardless of provider error content.
    for forbidden in ("Bearer ", "Authorization", "api-key", "api_key=sk-"):
        assert forbidden not in logged


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
            assert secret_name == "azure-openai-api-key"  # pragma: allowlist secret -- Key Vault secret NAME, not a value
            return "mock-secret-value-not-a-real-key"

    mock_client_cls.return_value.chat.completions.create = AsyncMock(
        return_value=_fake_completion()
    )
    provider = AzureOpenAIProvider(
        endpoint="https://example.openai.azure.com/",
        deployment="gpt-4o-mini",
        api_version="2024-10-21",
        secret_provider=_StubSecretProvider(),
        api_key_secret_name="azure-openai-api-key",  # pragma: allowlist secret -- Key Vault secret NAME, not a value
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


# Model-capability adaptation (PBI-03-05/PBI-03-06): reasoning-family models (gpt-5*, o1*,
# o3*, o4*) reject an explicit, non-default temperature outright — confirmed via a real Azure
# OpenAI deployment failure against gpt-5-mini. See src/llm/azure_openai_provider.py's
# _is_reasoning_model and docs/sprint_03/decisions.md for the full writeup.
#
# Azure OpenAI addresses deployments by an arbitrary alias (e.g. "chat"), never by the
# underlying model name — confirmed by a second real deployment failure when the capability
# check below was first implemented against `deployment` alone (it silently never fired,
# because the real deployment alias in this codebase's own Bicep template is "chat", which does
# not start with "gpt-5"). These tests therefore always use a realistic, distinct
# deployment/model_name pair (deployment="chat", model_name="gpt-5-mini") for the reasoning-
# model cases, not the same string for both, so this exact regression cannot reappear silently.
#
# PBI-03-06: real DEV deployment validation required POST /chat to actually succeed against
# gpt-5-mini, not just fail predictably — PBI-03-05's fail-fast LLMConfigurationError blocked
# every call outright. The provider now executes the call using the API's only supported
# temperature, surfacing the unpreserved determinism loudly via a WARNING log (asserted via
# caplog below) rather than a silent behavior change or a blocked request.


@patch("src.llm.azure_openai_provider.AsyncAzureOpenAI")
@patch("azure.identity.aio.DefaultAzureCredential")
@patch("azure.identity.aio.get_bearer_token_provider")
async def test_traditional_model_sends_explicit_temperature_and_max_completion_tokens(
    mock_token_provider: MagicMock, mock_credential_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    """A traditional (non-reasoning) model like gpt-4o-mini keeps receiving an explicit
    temperature exactly as configured — LLMGenerationSettings' deterministic temperature=0.0
    default is preserved unchanged for every model this provider already supported."""
    mock_client = mock_client_cls.return_value
    mock_client.chat.completions.create = AsyncMock(return_value=_fake_completion())
    provider = _build_provider(deployment="chat", model_name="gpt-4o-mini")

    await provider.generate(
        LLMRequest(messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")])
    )

    _, call_kwargs = mock_client.chat.completions.create.call_args
    assert call_kwargs["model"] == "chat"
    assert call_kwargs["temperature"] == 0.0
    assert "max_completion_tokens" in call_kwargs
    assert "max_tokens" not in call_kwargs


@patch("src.llm.azure_openai_provider.AsyncAzureOpenAI")
@patch("azure.identity.aio.DefaultAzureCredential")
@patch("azure.identity.aio.get_bearer_token_provider")
async def test_reasoning_model_capability_check_uses_model_name_not_deployment_alias(
    mock_token_provider: MagicMock, mock_credential_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    """Regression guard: the reasoning-family check must key off the real model name
    (model_name="gpt-5-mini"), not the arbitrary deployment alias ("chat") that is actually
    sent to the API as `model=`. A provider built with only `deployment="chat"` (no
    model_name) must NOT detect this as a reasoning model — it has no way to know the real
    model without model_name being explicitly supplied."""
    mock_client = mock_client_cls.return_value
    mock_client.chat.completions.create = AsyncMock(return_value=_fake_completion())
    provider = _build_provider(deployment="chat")  # model_name defaults to "chat", not gpt-5*

    await provider.generate(
        LLMRequest(messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")])
    )

    _, call_kwargs = mock_client.chat.completions.create.call_args
    assert call_kwargs["temperature"] == 0.0


@patch("src.llm.azure_openai_provider.AsyncAzureOpenAI")
@patch("azure.identity.aio.DefaultAzureCredential")
@patch("azure.identity.aio.get_bearer_token_provider")
async def test_reasoning_model_with_default_temperature_executes_and_logs_a_warning(
    mock_token_provider: MagicMock,
    mock_credential_cls: MagicMock,
    mock_client_cls: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """gpt-5-mini cannot honor LLMGenerationSettings' deterministic temperature=0.0 default
    (PBI-03-06, superseding PBI-03-05's fail-fast LLMConfigurationError): the call must still
    execute successfully against the real model — deployment validation requires a genuine
    200 from POST /chat — with the unpreserved determinism surfaced loudly via a WARNING log,
    never silently dropped and never blocking the request."""
    mock_client = mock_client_cls.return_value
    mock_client.chat.completions.create = AsyncMock(return_value=_fake_completion())
    provider = _build_provider(deployment="chat", model_name="gpt-5-mini")

    with caplog.at_level("WARNING", logger="src.llm.azure_openai_provider"):
        response = await provider.generate(
            LLMRequest(messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")])
        )

    assert response.text == "a mocked completion"
    mock_client.chat.completions.create.assert_called_once()
    _, call_kwargs = mock_client.chat.completions.create.call_args
    assert call_kwargs["model"] == "chat"  # the deployment alias, never the model name
    assert "temperature" not in call_kwargs
    assert "max_completion_tokens" in call_kwargs
    assert "max_tokens" not in call_kwargs
    assert any(
        "does not support the requested temperature" in record.message
        and "NOT preserved" in record.message
        for record in caplog.records
    ), "expected a WARNING documenting the unpreserved determinism, found none"


@patch("src.llm.azure_openai_provider.AsyncAzureOpenAI")
@patch("azure.identity.aio.DefaultAzureCredential")
@patch("azure.identity.aio.get_bearer_token_provider")
async def test_reasoning_model_with_fixed_temperature_succeeds_without_sending_temperature(
    mock_token_provider: MagicMock, mock_credential_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    """gpt-5-mini rejects an explicit temperature even when it equals the API's own fixed
    default (1.0) — a caller that explicitly opts into non-deterministic behavior via
    LLMGenerationSettings(temperature=1.0) can still generate successfully, with the
    temperature key omitted from the SDK call entirely. The deployment alias ("chat"), not the
    model name, is still what gets sent to the API as `model=`."""
    mock_client = mock_client_cls.return_value
    mock_client.chat.completions.create = AsyncMock(return_value=_fake_completion())
    provider = _build_provider(deployment="chat", model_name="gpt-5-mini")

    response = await provider.generate(
        LLMRequest(
            messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")],
            settings=LLMGenerationSettings(temperature=1.0),
        )
    )

    assert response.text == "a mocked completion"
    _, call_kwargs = mock_client.chat.completions.create.call_args
    assert call_kwargs["model"] == "chat"
    assert "temperature" not in call_kwargs
    assert "max_completion_tokens" in call_kwargs


# --- assistant tool_calls message mapping (PBI-04-03) -----------------------------------------
# Fixes a real, previously-undetected Azure OpenAI protocol violation: a role="tool" message is
# only valid immediately following the role="assistant" message whose own tool_calls it answers.
# See src/core/tool_calling/orchestrator.py and docs/sprint_04/decisions.md.


@patch("src.llm.azure_openai_provider.AsyncAzureOpenAI")
@patch("azure.identity.aio.DefaultAzureCredential")
@patch("azure.identity.aio.get_bearer_token_provider")
async def test_generate_maps_an_assistant_tool_calls_message_to_the_sdk_shape(
    mock_token_provider: MagicMock, mock_credential_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    """The exact fix under test: an ASSISTANT-role LLMMessage carrying tool_calls must be sent
    to the SDK as role="assistant" with a tool_calls array — the message Azure OpenAI requires
    to precede any role="tool" message answering it."""
    mock_client = mock_client_cls.return_value
    mock_client.chat.completions.create = AsyncMock(return_value=_fake_completion())
    provider = _build_provider()

    await provider.generate(
        LLMRequest(
            messages=[
                LLMMessage(role=LLMMessageRole.USER, content="hello"),
                LLMMessage(
                    role=LLMMessageRole.ASSISTANT,
                    content="",
                    tool_calls=[
                        ToolCallRequest(
                            call_id="call_1",
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
                    tool_call_id="call_1",
                ),
            ]
        )
    )

    _, call_kwargs = mock_client.chat.completions.create.call_args
    messages = call_kwargs["messages"]
    assert messages[0] == {"role": "user", "content": "hello"}
    assistant_message = messages[1]
    assert assistant_message["role"] == "assistant"
    assert assistant_message["content"] is None
    assert assistant_message["tool_calls"] == [
        {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "policy_lookup",
                "arguments": '{"policy_number": "SYN-POL-0001"}',
            },
        }
    ]
    assert messages[2] == {
        "role": "tool",
        "content": '{"success": true}',
        "tool_call_id": "call_1",
    }


@patch("src.llm.azure_openai_provider.AsyncAzureOpenAI")
@patch("azure.identity.aio.DefaultAzureCredential")
@patch("azure.identity.aio.get_bearer_token_provider")
async def test_generate_preserves_assistant_text_alongside_tool_calls_when_both_are_present(
    mock_token_provider: MagicMock, mock_credential_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    """A model that returns both text and tool_calls in one response (some models do) must
    still have its text preserved on the replayed assistant message, not silently dropped."""
    mock_client = mock_client_cls.return_value
    mock_client.chat.completions.create = AsyncMock(return_value=_fake_completion())
    provider = _build_provider()

    await provider.generate(
        LLMRequest(
            messages=[
                LLMMessage(role=LLMMessageRole.USER, content="hello"),
                LLMMessage(
                    role=LLMMessageRole.ASSISTANT,
                    content="Let me check that for you.",
                    tool_calls=[
                        ToolCallRequest(call_id="call_1", tool_name="policy_lookup", arguments=[])
                    ],
                ),
            ]
        )
    )

    _, call_kwargs = mock_client.chat.completions.create.call_args
    assert call_kwargs["messages"][1]["content"] == "Let me check that for you."


@patch("src.llm.azure_openai_provider.AsyncAzureOpenAI")
@patch("azure.identity.aio.DefaultAzureCredential")
@patch("azure.identity.aio.get_bearer_token_provider")
async def test_generate_treats_an_assistant_message_without_tool_calls_as_plain_text(
    mock_token_provider: MagicMock, mock_credential_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    """Regression guard: an ordinary assistant text message (tool_calls=None, the default)
    must still map to the plain {"role": "assistant", "content": ...} shape used before this
    PBI — the new branch must not swallow the existing, unaffected code path."""
    mock_client = mock_client_cls.return_value
    mock_client.chat.completions.create = AsyncMock(return_value=_fake_completion())
    provider = _build_provider()

    await provider.generate(
        LLMRequest(
            messages=[
                LLMMessage(role=LLMMessageRole.USER, content="hello"),
                LLMMessage(role=LLMMessageRole.ASSISTANT, content="a prior plain reply"),
            ]
        )
    )

    _, call_kwargs = mock_client.chat.completions.create.call_args
    assert call_kwargs["messages"][1] == {
        "role": "assistant",
        "content": "a prior plain reply",
    }


# ---------------------------------------------------------------------------------------------
# Resilience (Architecture Review Finding A-07): retry-with-backoff and circuit breaker,
# integrated into AzureOpenAIProvider.generate(). Retry/circuit-breaker delays are monkeypatched
# to near-zero so these tests run fast without weakening what they assert.
# ---------------------------------------------------------------------------------------------


@patch("src.llm.azure_openai_provider.AsyncAzureOpenAI")
@patch("azure.identity.aio.DefaultAzureCredential")
@patch("azure.identity.aio.get_bearer_token_provider")
async def test_generate_retries_a_transient_timeout_then_succeeds(
    mock_token_provider: MagicMock,
    mock_credential_cls: MagicMock,
    mock_client_cls: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.llm.azure_openai_provider as module

    monkeypatch.setattr(module, "_RETRY_BASE_DELAY_SECONDS", 0.001)
    monkeypatch.setattr(module, "_RETRY_MAX_DELAY_SECONDS", 0.002)

    mock_client = mock_client_cls.return_value
    mock_client.chat.completions.create = AsyncMock(
        side_effect=[
            APITimeoutError(request=_fake_request()),
            APITimeoutError(request=_fake_request()),
            _fake_completion("recovered on the third attempt"),
        ]
    )
    provider = _build_provider()

    response = await provider.generate(
        LLMRequest(messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")])
    )

    assert response.text == "recovered on the third attempt"
    assert mock_client.chat.completions.create.await_count == 3


@patch("src.llm.azure_openai_provider.AsyncAzureOpenAI")
@patch("azure.identity.aio.DefaultAzureCredential")
@patch("azure.identity.aio.get_bearer_token_provider")
async def test_generate_does_not_retry_a_non_transient_status_error(
    mock_token_provider: MagicMock,
    mock_credential_cls: MagicMock,
    mock_client_cls: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A business/content-shaped failure (APIStatusError, e.g. a 400) must fail on the first
    attempt — retrying it would never help and would only add latency."""
    import src.llm.azure_openai_provider as module

    monkeypatch.setattr(module, "_RETRY_BASE_DELAY_SECONDS", 0.001)

    mock_client = mock_client_cls.return_value
    mock_client.chat.completions.create = AsyncMock(
        side_effect=APIStatusError(
            "bad request", response=_fake_response(400), body=None
        )
    )
    provider = _build_provider()

    with pytest.raises(LLMProviderError):
        await provider.generate(
            LLMRequest(messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")])
        )

    assert mock_client.chat.completions.create.await_count == 1


@patch("src.llm.azure_openai_provider.AsyncAzureOpenAI")
@patch("azure.identity.aio.DefaultAzureCredential")
@patch("azure.identity.aio.get_bearer_token_provider")
async def test_generate_circuit_breaker_opens_and_fails_fast_after_repeated_failures(
    mock_token_provider: MagicMock,
    mock_credential_cls: MagicMock,
    mock_client_cls: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.llm.azure_openai_provider as module

    monkeypatch.setattr(module, "_RETRY_BASE_DELAY_SECONDS", 0.001)
    monkeypatch.setattr(module, "_RETRY_MAX_DELAY_SECONDS", 0.002)
    monkeypatch.setattr(module, "_RETRY_MAX_ATTEMPTS", 1)
    monkeypatch.setattr(module, "_CIRCUIT_BREAKER_FAILURE_THRESHOLD", 2)
    monkeypatch.setattr(module, "_CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS", 999.0)

    mock_client = mock_client_cls.return_value
    mock_client.chat.completions.create = AsyncMock(
        side_effect=APITimeoutError(request=_fake_request())
    )
    provider = _build_provider()
    request = LLMRequest(messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")])

    # First two calls each fail (1 attempt each, retries disabled above) — the second failure
    # reaches the circuit breaker's failure_threshold=2 and opens it.
    with pytest.raises(LLMTimeoutError):
        await provider.generate(request)
    with pytest.raises(LLMTimeoutError):
        await provider.generate(request)
    assert mock_client.chat.completions.create.await_count == 2

    # Third call: the circuit is open, so the SDK is never invoked again — fails fast with a
    # typed LLMProviderError (CircuitBreakerOpenError mapped at the LLMProvider boundary).
    with pytest.raises(LLMProviderError):
        await provider.generate(request)
    assert mock_client.chat.completions.create.await_count == 2

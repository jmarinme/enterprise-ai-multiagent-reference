"""AzureOpenAIProvider: production-shaped Azure OpenAI adapter.

Prefers Microsoft Entra ID (DefaultAzureCredential) authentication, since the `openai` SDK's
AsyncAzureOpenAI client natively supports it via azure_ad_token_provider. API-key auth, if
explicitly enabled via configuration, is obtained only through the existing SecretProvider
abstraction — never read directly from os.environ here.

Never exercised by the test suite against real Azure — MockLLMProvider is the default and
only provider the tests actually call (see src/llm/factory.py). This file is the only place
in the codebase that imports the openai/azure-identity SDKs.

Tool Calling (PBI-02-04): maps the same typed src.llm.models contracts (LLMToolDefinition,
ToolCallRequest, ToolCallArgument) onto the OpenAI/Azure OpenAI function-calling API shape
(`tools=`, `choices[0].message.tool_calls`, a `role="tool"` message). This provider only
translates the shape — it never decides which tools exist or are authorized; that remains
src.core.tool_calling.orchestrator.ToolCallingOrchestrator's job.
"""

from __future__ import annotations

import json
from typing import Any, cast

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncAzureOpenAI,
    RateLimitError,
)
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionToolMessageParam,
    ChatCompletionToolParam,
)
from openai.types.chat.chat_completion_message_custom_tool_call import (
    ChatCompletionMessageCustomToolCall,
)
from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
)

from src.domain.secret_provider import SecretProvider
from src.llm.exceptions import (
    LLMConfigurationError,
    LLMContentSafetyError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from src.llm.models import (
    LLMMessage,
    LLMMessageRole,
    LLMRequest,
    LLMResponse,
    LLMToolDefinition,
    LLMUsage,
    ToolCallArgument,
    ToolCallRequest,
)

_PROVIDER_NAME = "azure_openai"
_ENTRA_ID_SCOPE = "https://cognitiveservices.azure.com/.default"


class AzureOpenAIProvider:
    """LLMProvider implementation backed by Azure OpenAI."""

    def __init__(
        self,
        endpoint: str,
        deployment: str,
        api_version: str,
        secret_provider: SecretProvider | None = None,
        api_key_secret_name: str | None = None,
    ) -> None:
        if not endpoint:
            raise LLMConfigurationError(
                "AZURE_OPENAI_ENDPOINT must be set for the azure_openai provider"
            )
        if not deployment:
            raise LLMConfigurationError(
                "AZURE_OPENAI_DEPLOYMENT must be set for the azure_openai provider"
            )

        self._endpoint = endpoint
        self._deployment = deployment
        self._api_version = api_version
        self._secret_provider = secret_provider
        self._api_key_secret_name = api_key_secret_name
        self._client: AsyncAzureOpenAI | None = None
        self._credential_close: object | None = None

    async def _get_client(self) -> AsyncAzureOpenAI:
        if self._client is not None:
            return self._client

        if self._secret_provider is not None and self._api_key_secret_name:
            api_key = await self._secret_provider.get_secret(self._api_key_secret_name)
            self._client = AsyncAzureOpenAI(
                azure_endpoint=self._endpoint,
                api_key=api_key,
                api_version=self._api_version,
            )
        else:
            from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider

            credential = DefaultAzureCredential()
            self._credential_close = credential
            token_provider = get_bearer_token_provider(credential, _ENTRA_ID_SCOPE)
            self._client = AsyncAzureOpenAI(
                azure_endpoint=self._endpoint,
                azure_ad_token_provider=token_provider,
                api_version=self._api_version,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
        if self._credential_close is not None:
            await self._credential_close.close()  # type: ignore[attr-defined]

    async def generate(self, request: LLMRequest) -> LLMResponse:
        client = await self._get_client()
        model = request.settings.model or self._deployment

        try:
            messages = _to_openai_messages(request.messages)
            create_kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": request.settings.temperature,
                "max_tokens": request.settings.max_output_tokens,
                "timeout": request.settings.timeout_seconds,
            }
            if request.tools:
                create_kwargs["tools"] = _to_openai_tools(request.tools)
            completion = await client.chat.completions.create(**create_kwargs)
        except APITimeoutError as exc:
            raise LLMTimeoutError(_PROVIDER_NAME) from exc
        except RateLimitError as exc:
            raise LLMRateLimitError(_PROVIDER_NAME, str(exc)) from exc
        except APIConnectionError as exc:
            raise LLMProviderError(_PROVIDER_NAME, str(exc)) from exc
        except APIStatusError as exc:
            if "content_filter" in str(exc).lower():
                raise LLMContentSafetyError(_PROVIDER_NAME, str(exc)) from exc
            raise LLMProviderError(_PROVIDER_NAME, str(exc)) from exc

        choice = completion.choices[0]
        usage = completion.usage
        try:
            tool_calls = _from_openai_tool_calls(choice.message.tool_calls)
        except (json.JSONDecodeError, TypeError) as exc:
            # The SDK guarantees `.function.arguments` is a string, but not that it is valid
            # JSON — a malformed payload from the provider itself is a genuine, unexpected
            # provider failure, distinct from a syntactically valid argument set that simply
            # fails the resolved Tool's own input_model (ToolExecutor's job, never this one's).
            raise LLMProviderError(
                _PROVIDER_NAME, f"Malformed tool_call arguments from provider: {exc}"
            ) from exc

        return LLMResponse(
            text=choice.message.content or "",
            model=completion.model,
            usage=LLMUsage(
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
            ),
            tool_calls=tool_calls,
            correlation_id=request.correlation_id,
        )


def _to_openai_messages(messages: list[LLMMessage]) -> list[ChatCompletionMessageParam]:
    """Maps typed LLMMessages to the OpenAI SDK's per-role TypedDict shape, including the
    role="tool" shape a ToolCallRequest's result is fed back as (PBI-02-04)."""
    result: list[ChatCompletionMessageParam] = []
    for message in messages:
        if message.role == LLMMessageRole.TOOL:
            # tool_call_id is always set on a TOOL-role message — enforced by
            # src.core.tool_calling.orchestrator.ToolCallingOrchestrator, the only component
            # that ever constructs one.
            tool_message: ChatCompletionToolMessageParam = {
                "role": "tool",
                "content": message.content,
                "tool_call_id": message.tool_call_id or "",
            }
            result.append(tool_message)
        else:
            # cast: mypy cannot structurally narrow this dict to the specific TypedDict variant
            # openai's SDK expects per role from a plain literal string. The values are always
            # one of "system"/"user"/"assistant", all valid roles for this call — verified at
            # runtime by LLMMessageRole's own enum membership, not asserted blindly here.
            result.append(
                cast(
                    "ChatCompletionMessageParam",
                    {"role": message.role.value, "content": message.content},
                )
            )
    return result


def _to_openai_tools(tools: list[LLMToolDefinition]) -> list[ChatCompletionToolParam]:
    """Maps typed LLMToolDefinitions to OpenAI's function-calling `tools=` shape."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters_schema,
            },
        }
        for tool in tools
    ]


def _from_openai_tool_calls(
    raw_tool_calls: (
        list[ChatCompletionMessageFunctionToolCall | ChatCompletionMessageCustomToolCall] | None
    ),
) -> list[ToolCallRequest]:
    """Maps OpenAI's response tool_calls (each function.arguments is a JSON-encoded string)
    to typed ToolCallRequests. Raises json.JSONDecodeError/TypeError on a malformed payload —
    the caller (generate()) turns that into a typed LLMProviderError. Only "function"-type
    calls are mapped (the only type _to_openai_tools ever offers); a "custom" tool call would
    mean the provider returned a type this codebase never requested, so it is skipped rather
    than guessed at."""
    if not raw_tool_calls:
        return []
    result: list[ToolCallRequest] = []
    for raw_call in raw_tool_calls:
        if raw_call.type != "function":
            continue
        raw_arguments = json.loads(raw_call.function.arguments)
        if not isinstance(raw_arguments, dict):
            raise TypeError(
                f"tool_call arguments for '{raw_call.function.name}' did not decode to an object"
            )
        result.append(
            ToolCallRequest(
                call_id=raw_call.id,
                tool_name=raw_call.function.name,
                arguments=[
                    ToolCallArgument(name=name, value=value)
                    for name, value in raw_arguments.items()
                ],
            )
        )
    return result

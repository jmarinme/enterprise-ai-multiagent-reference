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
import logging
from typing import Any, cast

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncAzureOpenAI,
    RateLimitError,
)
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageFunctionToolCallParam,
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

from src.core.resilience import CircuitBreaker, CircuitBreakerOpenError, retry_with_backoff
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

logger = logging.getLogger(__name__)

_PROVIDER_NAME = "azure_openai"
_ENTRA_ID_SCOPE = "https://cognitiveservices.azure.com/.default"

# Reasoning-family models (PBI-03-05/PBI-03-06): confirmed via real Azure OpenAI deployment
# failures against gpt-5-mini ("Unsupported value: 'temperature' does not support 0.0 with
# this model. Only the default (1) value is supported.") that this model family accepts no
# explicit temperature at all — only the API's own built-in default. This is documented,
# industry-wide reasoning-model behavior (OpenAI's o-series and gpt-5 family), not specific to
# this one model version. Traditional chat-completions models (gpt-4o*, gpt-4.1*, gpt-3.5*, ...)
# are unaffected and keep receiving an explicit temperature exactly as before. See
# docs/sprint_03/decisions.md (PBI-03-05, PBI-03-06) for the full capability-gap writeup.
_REASONING_MODEL_PREFIXES = ("gpt-5", "o1", "o3", "o4")
_REASONING_MODEL_FIXED_TEMPERATURE = 1.0

# Resilience (Architecture Review Finding A-07, CLAUDE.md principle #9): retries only genuinely
# transient SDK exceptions (connection failure, timeout, rate limit) — never APIStatusError,
# which covers both retryable 5xx AND non-retryable 4xx/content-filter business outcomes the
# SDK doesn't distinguish by exception type alone, so this deliberately stays conservative
# rather than parsing status codes out of APIStatusError. Circuit breaker is per-process, one
# instance for this provider's lifetime (matches the existing @lru_cache singleton scope).
_RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
)
_RETRY_MAX_ATTEMPTS = 3
_RETRY_BASE_DELAY_SECONDS = 0.5
_RETRY_MAX_DELAY_SECONDS = 8.0
_CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
_CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS = 30.0


def _log_provider_status_error(exc: APIStatusError, deployment: str, api_version: str) -> None:
    """DEV diagnostic — logs only four sanitized, whitelisted fields (`message`/`type`/`code`/
    `param`) extracted from the SDK's own typed exception (never str(exc), which can embed
    provider-formatted request context, and never the full body). Confirmed live (PBI-14-13,
    correlationId ce901473-5337-4e28-acad-8b853ccca2b4) that Azure's SDK exposes APIStatusError
    .body FLAT — message/type/param/code as top-level keys, not wrapped in an {"error": {...}}
    envelope as OpenAI's own docs/most examples show; the original {"error": {...}} extraction
    silently produced None for every field against a real Azure response. Safe by construction:
    these four fields are Azure's own schema/request-validation description (what was wrong
    with the SCHEMA/PARAMETERS), never conversation content — Azure never echoes the raw prompt
    or user message back inside a 4xx error body for this failure class. No bearer token, API
    key, Authorization header, raw prompt, raw user message, or raw/full request or response
    body is ever read or logged here. `message` is truncated defensively in case a future,
    different error class ever embeds something unexpectedly long.
    """
    body = exc.body if isinstance(exc.body, dict) else {}
    request_id = None
    response = getattr(exc, "response", None)
    if response is not None:
        request_id = response.headers.get("x-ms-request-id") or response.headers.get(
            "x-request-id"
        )
    provider_message = body.get("message")
    if isinstance(provider_message, str) and len(provider_message) > 500:
        provider_message = provider_message[:500] + "...(truncated)"
    logger.error(
        "azure_openai_provider_error: http_status=%s provider_error_code=%s "
        "provider_error_type=%s provider_error_param=%s provider_error_message=%s "
        "request_id=%s deployment=%s api_version=%s",
        exc.status_code,
        body.get("code"),
        body.get("type"),
        body.get("param"),
        provider_message,
        request_id,
        deployment,
        api_version,
    )


def _is_reasoning_model(model: str) -> bool:
    """True for OpenAI/Azure OpenAI "reasoning-family" models, which reject a caller-supplied
    temperature other than the API's own fixed default."""
    return model.startswith(_REASONING_MODEL_PREFIXES)


class AzureOpenAIProvider:
    """LLMProvider implementation backed by Azure OpenAI."""

    def __init__(
        self,
        endpoint: str,
        deployment: str,
        api_version: str,
        secret_provider: SecretProvider | None = None,
        api_key_secret_name: str | None = None,
        model_name: str | None = None,
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
        # model_name (PBI-03-05): the underlying model (e.g. "gpt-5-mini"), used only for
        # reasoning-family capability detection — distinct from `deployment`, an arbitrary
        # Azure OpenAI deployment alias (e.g. "chat") that is what actually gets sent to the
        # API as `model=`. Defaults to `deployment` when not given so a caller that never
        # passes it behaves exactly as before this PBI (the alias happens to be usable as a
        # capability hint only in the pre-PBI-03-05 tests, which use "gpt-4o-mini" as both).
        self._model_name = model_name or deployment
        self._client: AsyncAzureOpenAI | None = None
        self._credential_close: object | None = None
        self._circuit_breaker = CircuitBreaker(
            _PROVIDER_NAME,
            failure_threshold=_CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            reset_timeout_seconds=_CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS,
        )

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

    async def health_check(self) -> bool:
        """`models.list()` — a lightweight metadata/introspection call, never a real
        completion (no token cost, no prompt content sent). Bypasses the retry/circuit-breaker
        wrapping `generate()` uses (a readiness probe should reflect the dependency's state
        right now, not spend several seconds retrying) and never raises: any failure (auth,
        network, timeout) is caught and reported as False."""
        import asyncio

        try:
            client = await self._get_client()
            async with asyncio.timeout(5.0):
                await client.models.list()
            return True
        except Exception:  # noqa: BLE001 -- a health check must never itself raise; the Protocol's own contract (src/llm/provider.py) guarantees this method reports False on any failure rather than propagating.
            return False

    async def generate(self, request: LLMRequest) -> LLMResponse:
        client = await self._get_client()
        # model: what is actually sent to the API as `model=` — an Azure OpenAI deployment
        # alias (e.g. "chat"), never the underlying model name. self._model_name (constructor-
        # level, PBI-03-05) is the real model name (e.g. "gpt-5-mini") used only for capability
        # detection below — the two are deliberately kept distinct; see __init__'s docstring.
        model = request.settings.model or self._deployment
        is_reasoning = _is_reasoning_model(self._model_name)
        temperature_not_honored = is_reasoning and request.settings.temperature != (
            _REASONING_MODEL_FIXED_TEMPERATURE
        )

        if temperature_not_honored:
            # A real, permanent capability gap, not a bug to paper over: this reasoning-family
            # model rejects any explicit temperature outright, including one that matches its
            # own fixed default, and LLMGenerationSettings' own temperature=0.0 default
            # (src/llm/models.py) encodes a deliberate, deterministic-response design choice
            # made by callers (agents) that this provider must never silently pretend to
            # preserve. PBI-03-05 made this fail loudly (a typed LLMConfigurationError,
            # blocking every call); PBI-03-06 changes this to the minimum provider-level
            # compatible behavior that still executes the model, per explicit instruction —
            # the call proceeds using the API's own fixed temperature, and this is surfaced
            # loudly via a WARNING log (never silent), not via a return-value change, since
            # LLMResponse's contract is deliberately left untouched (no LLM-abstraction
            # redesign). See docs/sprint_03/decisions.md (PBI-03-05, PBI-03-06).
            logger.warning(
                "azure_openai reasoning-family model capability gap: model=%r "
                "(deployment=%r) does not support the requested temperature=%r; executing "
                "with the API's fixed default (%r) instead. Deterministic response behavior "
                "is NOT preserved for this call.",
                self._model_name,
                model,
                request.settings.temperature,
                _REASONING_MODEL_FIXED_TEMPERATURE,
            )

        try:
            messages = _to_openai_messages(request.messages)
            create_kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                # max_completion_tokens, not max_tokens (PBI-03-05): current-generation models
                # (e.g. gpt-5-mini) reject max_tokens outright ("Unsupported parameter"), and
                # max_completion_tokens is OpenAI's now-recommended replacement, accepted by
                # every model this provider currently targets — confirmed via a real deployment
                # failure. See docs/sprint_03/decisions.md.
                "max_completion_tokens": request.settings.max_output_tokens,
                "timeout": request.settings.timeout_seconds,
            }
            if not is_reasoning:
                # Reasoning-family models reject an explicit temperature outright, even when it
                # equals their own fixed default — omitting the key here is required for every
                # reasoning-family call, not just the ones where the requested value differs
                # (see temperature_not_honored above for the audit-log path covering that case).
                create_kwargs["temperature"] = request.settings.temperature
            if request.tools:
                create_kwargs["tools"] = _to_openai_tools(request.tools)
            if request.response_schema is not None:
                create_kwargs["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": request.response_schema.name,
                        "schema": request.response_schema.schema_,
                        "strict": request.response_schema.strict,
                    },
                }

            async def _call_completions_api() -> Any:
                return await client.chat.completions.create(**create_kwargs)

            async def _resilient_call() -> Any:
                return await retry_with_backoff(
                    _call_completions_api,
                    retryable_exceptions=_RETRYABLE_EXCEPTIONS,
                    max_attempts=_RETRY_MAX_ATTEMPTS,
                    base_delay_seconds=_RETRY_BASE_DELAY_SECONDS,
                    max_delay_seconds=_RETRY_MAX_DELAY_SECONDS,
                    operation_name=f"{_PROVIDER_NAME} chat.completions.create",
                )

            completion = await self._circuit_breaker.call(_resilient_call)
        except CircuitBreakerOpenError as exc:
            raise LLMProviderError(_PROVIDER_NAME, str(exc)) from exc
        except APITimeoutError as exc:
            raise LLMTimeoutError(_PROVIDER_NAME) from exc
        except RateLimitError as exc:
            raise LLMRateLimitError(_PROVIDER_NAME, str(exc)) from exc
        except APIConnectionError as exc:
            raise LLMProviderError(_PROVIDER_NAME, str(exc)) from exc
        except APIStatusError as exc:
            _log_provider_status_error(exc, model, self._api_version)
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
    role="tool" shape a ToolCallRequest's result is fed back as (PBI-02-04), and the
    role="assistant" + tool_calls shape that same result must be a response *to* (PBI-04-03)."""
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
        elif message.role == LLMMessageRole.ASSISTANT and message.tool_calls:
            # PBI-04-03: replays the model's own prior tool-calling request as history — the
            # OpenAI/Azure OpenAI protocol requires this to immediately precede the TOOL
            # message(s) answering it. content is empty for essentially every real tool-calling
            # turn (the model requests a call instead of writing text) — None, not "", matches
            # the SDK's own documented "omitted when tool_calls is set" convention.
            assistant_message: ChatCompletionAssistantMessageParam = {
                "role": "assistant",
                "content": message.content or None,
                "tool_calls": _to_openai_tool_calls(message.tool_calls),
            }
            result.append(assistant_message)
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


def _to_openai_tool_calls(
    tool_calls: list[ToolCallRequest],
) -> list[ChatCompletionMessageFunctionToolCallParam]:
    """Maps typed ToolCallRequests back to OpenAI's assistant-message tool_calls shape — the
    exact inverse of _from_openai_tool_calls, used to replay the model's own prior tool-call
    request as conversation history (PBI-04-03)."""
    return [
        {
            "id": call.call_id,
            "type": "function",
            "function": {
                "name": call.tool_name,
                "arguments": json.dumps(
                    {argument.name: argument.value for argument in call.arguments}
                ),
            },
        }
        for call in tool_calls
    ]


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

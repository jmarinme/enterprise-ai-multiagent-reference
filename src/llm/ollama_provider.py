"""OllamaLLMProvider: local LLM adapter using a self-hosted Ollama server's REST API
(https://github.com/ollama/ollama/blob/main/docs/api.md), for fully local, zero-Azure-cost
development and demo runs (PBI-03-01).

aiohttp is imported lazily, inside this module only, so the default mock provider and the
Azure OpenAI provider never require it to be installed or reachable — the same pattern
AzureOpenAIProvider already established for the openai/azure-identity SDKs. aiohttp is already
a declared, installed dependency of this project's other Azure extras (cosmos, keyvault,
azureopenai, azuresearch); this is the first module to import and use it directly, added as a
new `ollama` extra in pyproject.toml (see docs/sprint_03/decisions.md).

Never exercised by the test suite against a real Ollama server — every test in
tests/unit/llm/test_ollama_provider.py fully mocks the aiohttp client, exactly like
AzureOpenAIProvider's own tests mock the openai SDK.

Tool Calling (PBI-02-04): request.tools/response.tool_calls are mapped to/from Ollama's
documented OpenAI-compatible `tools=`/`message.tool_calls` shape, with two Ollama-specific
differences from AzureOpenAIProvider's own mapping:
  - Ollama's tool_calls carry no id — one is synthesized deterministically per response
    (`ollama-call-<index>`), since ToolCallRequest.call_id is required.
  - Ollama's `function.arguments` arrives as an already-parsed JSON object (a dict), not a
    JSON-encoded string the way OpenAI's API returns it — no json.loads() needed.
This mapping is implemented per Ollama's public API documentation but has NOT been
live-verified against a real Ollama server with a tool-calling-capable model, since neither
was available in this development environment (see docs/sprint_03/decisions.md). This is safe
by construction, not merely by good fortune: a model that does not support tool calling (or an
Ollama version that ignores the `tools` field) simply returns no `tool_calls`, which
src.core.tool_calling.orchestrator.ToolCallingOrchestrator already treats as "the LLM chose not
to call anything" — the deterministic Claims workflow this provider feeds can never be put at
risk by a gap in this mapping.
"""

from __future__ import annotations

from typing import Any

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
    LLMResponse,
    LLMToolDefinition,
    LLMUsage,
    ToolCallArgument,
    ToolCallRequest,
)

_PROVIDER_NAME = "ollama"


class OllamaLLMProvider:
    """LLMProvider implementation backed by a local (or host-reachable) Ollama server."""

    def __init__(self, base_url: str, model: str, timeout_seconds: float = 60.0) -> None:
        if not base_url:
            raise LLMConfigurationError("OLLAMA_BASE_URL must be set for the ollama provider")
        if not model:
            raise LLMConfigurationError("OLLAMA_MODEL must be set for the ollama provider")

        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds

    async def generate(self, request: LLMRequest) -> LLMResponse:
        import aiohttp

        model = request.settings.model or self._model
        payload: dict[str, Any] = {
            "model": model,
            "messages": _to_ollama_messages(request.messages),
            "stream": False,
            "options": {
                "temperature": request.settings.temperature,
                "num_predict": request.settings.max_output_tokens,
            },
        }
        if request.tools:
            payload["tools"] = _to_ollama_tools(request.tools)

        # Ollama's own configured timeout (local inference can legitimately take far longer
        # than a cloud API call) takes precedence over LLMGenerationSettings.timeout_seconds'
        # cloud-API-tuned 30s default — a deliberate divergence from AzureOpenAIProvider, see
        # docs/sprint_03/decisions.md.
        timeout = aiohttp.ClientTimeout(total=self._timeout_seconds)

        try:
            async with (
                aiohttp.ClientSession(timeout=timeout) as session,
                session.post(f"{self._base_url}/api/chat", json=payload) as response,
            ):
                response.raise_for_status()
                data = await response.json()
        except TimeoutError as exc:
            raise LLMTimeoutError(_PROVIDER_NAME) from exc
        except aiohttp.ClientResponseError as exc:
            if exc.status == 429:
                raise LLMRateLimitError(_PROVIDER_NAME, str(exc)) from exc
            raise LLMProviderError(_PROVIDER_NAME, str(exc)) from exc
        except aiohttp.ClientConnectionError as exc:
            raise LLMProviderError(_PROVIDER_NAME, str(exc)) from exc
        except aiohttp.ClientError as exc:
            raise LLMProviderError(_PROVIDER_NAME, str(exc)) from exc

        message = data.get("message") or {}
        prompt_tokens = data.get("prompt_eval_count") or 0
        completion_tokens = data.get("eval_count") or 0

        return LLMResponse(
            text=message.get("content") or "",
            model=data.get("model") or model,
            usage=LLMUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
            tool_calls=_from_ollama_tool_calls(message.get("tool_calls")),
            correlation_id=request.correlation_id,
        )

    async def health_check(self) -> bool:
        """GET /api/tags — Ollama's own lightweight "list installed models" endpoint, no
        inference performed. A short, fixed timeout (never this provider's own, potentially
        long, generate()-tuned timeout_seconds) so a slow/unreachable Ollama server cannot
        stall a readiness probe."""
        import aiohttp

        try:
            timeout = aiohttp.ClientTimeout(total=5.0)
            async with (
                aiohttp.ClientSession(timeout=timeout) as session,
                session.get(f"{self._base_url}/api/tags") as response,
            ):
                return response.status == 200
        except aiohttp.ClientError:
            return False
        except TimeoutError:
            return False


def _to_ollama_messages(messages: list[LLMMessage]) -> list[dict[str, Any]]:
    """Maps typed LLMMessages to Ollama's chat message shape — structurally the same
    role/content dict OpenAI uses, including role="tool" for a fed-back ToolCallResult, and
    (PBI-04-03) role="assistant" + tool_calls for the request that result answers, matching
    the same OpenAI-compatible protocol AzureOpenAIProvider's own mapping now sends. Ollama's
    own tool_calls shape carries no id (see module docstring) and arguments as a plain object,
    not a JSON-encoded string."""
    result: list[dict[str, Any]] = []
    for message in messages:
        entry: dict[str, Any] = {"role": message.role.value, "content": message.content}
        if message.role == LLMMessageRole.TOOL and message.tool_call_id:
            entry["tool_call_id"] = message.tool_call_id
        elif message.role == LLMMessageRole.ASSISTANT and message.tool_calls:
            entry["tool_calls"] = [
                {
                    "function": {
                        "name": call.tool_name,
                        "arguments": {argument.name: argument.value for argument in call.arguments},
                    }
                }
                for call in message.tool_calls
            ]
        result.append(entry)
    return result


def _to_ollama_tools(tools: list[LLMToolDefinition]) -> list[dict[str, Any]]:
    """Maps typed LLMToolDefinitions to Ollama's documented OpenAI-compatible tools= shape."""
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


def _from_ollama_tool_calls(raw_tool_calls: Any) -> list[ToolCallRequest]:
    """Maps Ollama's response tool_calls to typed ToolCallRequests. Unlike OpenAI, Ollama does
    not assign each call an id (one is synthesized here) and arguments arrive as an
    already-parsed dict (no JSON string to decode)."""
    if not raw_tool_calls:
        return []
    result: list[ToolCallRequest] = []
    for index, raw_call in enumerate(raw_tool_calls):
        function = raw_call.get("function") or {}
        raw_arguments = function.get("arguments") or {}
        result.append(
            ToolCallRequest(
                call_id=f"ollama-call-{index}",
                tool_name=function.get("name", ""),
                arguments=[
                    ToolCallArgument(name=name, value=value)
                    for name, value in raw_arguments.items()
                ],
            )
        )
    return result

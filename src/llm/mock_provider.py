"""MockLLMProvider: completely deterministic, no Azure connectivity, no business logic.

The default LLM_PROVIDER (see src/llm/factory.py) — every local dev run and every test uses
this provider unless AzureOpenAIProvider is explicitly configured.

Tool Calling (PBI-02-04): tool_call_plan is an optional, test-only, constructor-supplied
script of ToolCallRequests. The default (None) makes generate() behave byte-identically to
before this PBI for every existing caller — none of which ever set request.tools — so this is
a purely additive capability, not a change to any prior behavior. When a plan IS supplied and
the caller offers tool definitions, MockLLMProvider deterministically returns the subset of
its scripted plan whose tool_name is actually offered, exactly once per conversation (it never
re-requests a tool once a TOOL-role message — the result of a prior request — is already
present in history), which is what prevents MockLLMProvider itself from ever looping forever.
"""

from __future__ import annotations

from src.llm.models import LLMMessageRole, LLMRequest, LLMResponse, LLMUsage, ToolCallRequest


class MockLLMProvider:
    """Deterministic LLMProvider for local development and tests.

    The response text is derived only from the request's own content (message count and the
    last user message's length) — never randomness, never a clock, never any synthetic
    business data. The same request always produces the same response.
    """

    model_name = "mock-llm"

    def __init__(self, tool_call_plan: list[ToolCallRequest] | None = None) -> None:
        self._tool_call_plan = tool_call_plan or []

    async def generate(self, request: LLMRequest) -> LLMResponse:
        if self._should_request_tool_calls(request):
            requested = self._matching_tool_calls(request)
            if requested:
                return LLMResponse(
                    text="",
                    model=self.model_name,
                    usage=LLMUsage(),
                    tool_calls=requested,
                    correlation_id=request.correlation_id,
                )

        last_user_message = next(
            (m.content for m in reversed(request.messages) if m.role == LLMMessageRole.USER),
            "",
        )
        prompt_tokens = sum(len(m.content.split()) for m in request.messages)
        completion_text = (
            "This is a deterministic mock LLM response. "
            f"It acknowledges a message of {len(last_user_message)} characters "
            f"across {len(request.messages)} message(s)."
        )
        completion_tokens = len(completion_text.split())

        return LLMResponse(
            text=completion_text,
            model=self.model_name,
            usage=LLMUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
            correlation_id=request.correlation_id,
        )

    def _should_request_tool_calls(self, request: LLMRequest) -> bool:
        if not self._tool_call_plan or not request.tools:
            return False
        return not any(message.role == LLMMessageRole.TOOL for message in request.messages)

    def _matching_tool_calls(self, request: LLMRequest) -> list[ToolCallRequest]:
        offered_names = {tool_definition.name for tool_definition in request.tools}
        return [call for call in self._tool_call_plan if call.tool_name in offered_names]

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

Structured output (PBI-14-03): structured_response_plan is an optional, test-only,
constructor-supplied mapping of LLMResponseSchema.name -> a pre-encoded JSON text to return
verbatim as LLMResponse.text whenever request.response_schema is set and its name is a key in
this mapping. None (the default) leaves every existing caller unaffected — no existing call
site sets request.response_schema. A caller that sets response_schema without a matching plan
entry gets a clear, typed failure rather than a silently wrong (non-JSON) mock response, since
callers expecting structured output always parse the response as JSON.

structured_response_sequence is the same idea but scripts a different JSON text per successive
call for a given schema name — needed to exercise a multi-turn conversational regression
scenario (e.g. PBI-14-03's own three exact regression scenarios) where each turn's semantic
interpretation should plausibly differ. Takes precedence over structured_response_plan for a
schema name present in both. The sequence is consumed one entry per call; once exhausted, the
last entry repeats for any further call — never raises once at least one entry was supplied.
"""

from __future__ import annotations

from src.llm.exceptions import LLMProviderError
from src.llm.models import LLMMessageRole, LLMRequest, LLMResponse, LLMUsage, ToolCallRequest


class MockLLMProvider:
    """Deterministic LLMProvider for local development and tests.

    The response text is derived only from the request's own content (message count and the
    last user message's length) — never randomness, never a clock, never any synthetic
    business data. The same request always produces the same response.
    """

    model_name = "mock-llm"

    def __init__(
        self,
        tool_call_plan: list[ToolCallRequest] | None = None,
        structured_response_plan: dict[str, str] | None = None,
        structured_response_sequence: dict[str, list[str]] | None = None,
    ) -> None:
        self._tool_call_plan = tool_call_plan or []
        self._structured_response_plan = structured_response_plan or {}
        self._structured_response_sequence = structured_response_sequence or {}
        self._structured_response_sequence_index: dict[str, int] = {}

    async def generate(self, request: LLMRequest) -> LLMResponse:
        if request.response_schema is not None:
            return self._generate_structured(request)
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

    def _generate_structured(self, request: LLMRequest) -> LLMResponse:
        schema_name = request.response_schema.name if request.response_schema else ""
        scripted_text = self._next_from_sequence(schema_name)
        if scripted_text is None:
            scripted_text = self._structured_response_plan.get(schema_name)
        if scripted_text is None:
            raise LLMProviderError(
                "mock",
                f"MockLLMProvider received response_schema.name={schema_name!r} with no "
                "matching entry in structured_response_plan — supply one via the "
                "MockLLMProvider(structured_response_plan={...}) constructor argument.",
            )
        prompt_tokens = sum(len(m.content.split()) for m in request.messages)
        completion_tokens = len(scripted_text.split())
        return LLMResponse(
            text=scripted_text,
            model=self.model_name,
            usage=LLMUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
            correlation_id=request.correlation_id,
        )

    def _next_from_sequence(self, schema_name: str) -> str | None:
        sequence = self._structured_response_sequence.get(schema_name)
        if not sequence:
            return None
        index = self._structured_response_sequence_index.get(schema_name, 0)
        entry = sequence[min(index, len(sequence) - 1)]
        self._structured_response_sequence_index[schema_name] = index + 1
        return entry

    def _should_request_tool_calls(self, request: LLMRequest) -> bool:
        if not self._tool_call_plan or not request.tools:
            return False
        return not any(message.role == LLMMessageRole.TOOL for message in request.messages)

    def _matching_tool_calls(self, request: LLMRequest) -> list[ToolCallRequest]:
        offered_names = {tool_definition.name for tool_definition in request.tools}
        return [call for call in self._tool_call_plan if call.tool_name in offered_names]

    async def health_check(self) -> bool:
        """No external dependency — always reachable."""
        return True

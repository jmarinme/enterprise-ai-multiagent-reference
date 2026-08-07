"""MockLLMProvider: completely deterministic, no Azure connectivity, no business logic.

The default LLM_PROVIDER (see src/llm/factory.py) — every local dev run and every test uses
this provider unless AzureOpenAIProvider is explicitly configured.
"""

from __future__ import annotations

from src.llm.models import LLMMessageRole, LLMRequest, LLMResponse, LLMUsage


class MockLLMProvider:
    """Deterministic LLMProvider for local development and tests.

    The response text is derived only from the request's own content (message count and the
    last user message's length) — never randomness, never a clock, never any synthetic
    business data. The same request always produces the same response.
    """

    model_name = "mock-llm"

    async def generate(self, request: LLMRequest) -> LLMResponse:
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

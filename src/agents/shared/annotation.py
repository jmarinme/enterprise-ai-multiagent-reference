"""Shared prompt+LLM annotation helper for multi-turn Agents.

Extracted from ClaimsAgent (PBI-01-05) and BrokerAgent (PBI-01-06), which had implemented
this exact logic twice, byte-for-byte identical apart from already-parameterized inputs
(prompt identifier, agent name, intent). PromptManager and LLMProvider are invoked every turn
so both frameworks stay genuinely wired (provable via the returned [prompt=...]/[llm=...]
annotation), but neither's output ever becomes response_text itself — the caller's
deterministic, Tool-sourced text is the only source of a business fact (CLAUDE.md §3).
"""

from __future__ import annotations

from src.llm.exceptions import LLMError
from src.llm.models import LLMGenerationSettings, LLMMessage, LLMMessageRole, LLMRequest
from src.llm.provider import LLMProvider
from src.prompts.exceptions import PromptError
from src.prompts.manager import PromptManager
from src.prompts.models import PromptRenderContext


async def annotate_with_prompt_and_llm(
    response_text: str,
    prompt_identifier: str,
    prompt_manager: PromptManager,
    llm_provider: LLMProvider,
    render_context: PromptRenderContext,
    user_message: str,
    correlation_id: str | None,
    conversation_id: str | None,
    user_id: str | None,
) -> str:
    """Render prompt_identifier, call the LLM, and append a provable annotation of both
    invocations to response_text. Degrades gracefully to response_text alone (or with only
    the prompt annotation) if PromptManager or LLMProvider fails — CLAUDE.md §11 requires a
    safe, understandable response even when a downstream framework fails."""
    try:
        rendered_prompt = await prompt_manager.render(prompt_identifier, render_context)
    except PromptError:
        return response_text

    prompt_annotation = f"[prompt={rendered_prompt.identifier}@{rendered_prompt.metadata.version}]"

    try:
        llm_response = await llm_provider.generate(
            LLMRequest(
                messages=[
                    LLMMessage(role=LLMMessageRole.SYSTEM, content=rendered_prompt.text),
                    LLMMessage(role=LLMMessageRole.USER, content=user_message),
                ],
                settings=LLMGenerationSettings(),
                correlation_id=correlation_id,
                conversation_id=conversation_id,
                user_id=user_id,
            )
        )
    except LLMError:
        return f"{response_text} {prompt_annotation}"

    return f"{response_text} {prompt_annotation} [llm={llm_response.model}]"

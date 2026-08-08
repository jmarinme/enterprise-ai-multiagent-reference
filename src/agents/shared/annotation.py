"""Shared prompt+LLM annotation helper for multi-turn Agents.

Extracted from ClaimsAgent (PBI-01-05) and BrokerAgent (PBI-01-06), which had implemented
this exact logic twice, byte-for-byte identical apart from already-parameterized inputs
(prompt identifier, agent name, intent). PromptManager and LLMProvider are invoked every turn
so both frameworks stay genuinely wired (provable via the returned [prompt=...]/[llm=...]
diagnostic string), but neither's output ever becomes response_text itself — the caller's
deterministic, Tool-sourced text is the only source of a business fact (CLAUDE.md §3).

PBI-04-04: the diagnostic string is no longer appended to the user-visible response text —
prompt identifiers/versions and LLM model names are technical details end users must never see
(CLAUDE.md's Sprint 04 UX mandate). Callers now receive the diagnostic separately and store it
only in AgentResponse.metadata (never rendered by the Web UI, available for logs/observability
per CLAUDE.md §10's "redacted metadata").
"""

from __future__ import annotations

from src.llm.exceptions import LLMError
from src.llm.models import LLMGenerationSettings, LLMMessage, LLMMessageRole, LLMRequest
from src.llm.provider import LLMProvider
from src.prompts.exceptions import PromptError
from src.prompts.manager import PromptManager
from src.prompts.models import PromptRenderContext


async def annotate_with_prompt_and_llm(
    prompt_identifier: str,
    prompt_manager: PromptManager,
    llm_provider: LLMProvider,
    render_context: PromptRenderContext,
    user_message: str,
    correlation_id: str | None,
    conversation_id: str | None,
    user_id: str | None,
) -> str:
    """Render prompt_identifier, call the LLM, and return a provable diagnostic string
    ("[prompt=...] [llm=...]") of both invocations — a metadata-only value, never appended to
    or derived from the caller's own user-visible response text (PBI-04-04). Degrades
    gracefully to an empty string (or a prompt-only diagnostic) if PromptManager or LLMProvider
    fails — CLAUDE.md §11 requires a safe, understandable response even when a downstream
    framework fails; the caller's own response text is untouched by any of these failure
    modes, since this function never sees or returns it."""
    try:
        rendered_prompt = await prompt_manager.render(prompt_identifier, render_context)
    except PromptError:
        return ""

    prompt_diagnostic = f"[prompt={rendered_prompt.identifier}@{rendered_prompt.metadata.version}]"

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
        return prompt_diagnostic

    return f"{prompt_diagnostic} [llm={llm_response.model}]"

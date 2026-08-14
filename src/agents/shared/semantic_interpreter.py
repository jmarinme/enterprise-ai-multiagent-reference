"""Shared semantic interpretation (PBI-14-03) — repurposes the ONE LLM call every specialist
Agent already made every turn (previously src.agents.shared.annotation.
annotate_with_prompt_and_llm, whose actual LLM-generated text was entirely discarded in favor
of a fixed `[prompt=...] [llm=...]` diagnostic string) to instead return a real, structured,
typed SemanticInterpretation. LLM calls per turn are unchanged by this: exactly one, same as
before this PBI — see docs/sprint_14/decisions.md.

Requests structured output (src.llm.models.LLMResponseSchema, threaded through to Azure
OpenAI's `response_format=json_schema` by src.llm.azure_openai_provider) so the response is
guaranteed to be JSON shaped like the caller's own domain schema — never chain-of-thought,
never free text, never anything the caller must additionally parse out of prose.

Degrades gracefully to a low-confidence, empty interpretation on any Prompt/LLM/parse failure,
exactly like annotate_with_prompt_and_llm did — this must never block the deterministic
business flow (CLAUDE.md §11). Callers still receive a diagnostic string for
AgentResponse.metadata, same as before.
"""

from __future__ import annotations

import logging
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from src.llm.exceptions import LLMError
from src.llm.models import (
    LLMGenerationSettings,
    LLMMessage,
    LLMMessageRole,
    LLMRequest,
    LLMResponseSchema,
)
from src.llm.provider import LLMProvider
from src.prompts.exceptions import PromptError
from src.prompts.manager import PromptManager
from src.prompts.models import PromptRenderContext

logger = logging.getLogger(__name__)

SchemaT = TypeVar("SchemaT", bound=BaseModel)

# A genuine parse/validation failure or a degraded (Prompt/LLM error) path both resolve to the
# same safe, empty interpretation: unknown intent at zero confidence, no entities, no
# confirmation — every downstream deterministic merge/routing/confirmation step already treats
# "nothing usable this turn" as a no-op, exactly as if this call had never been made.
_FALLBACK_INTENT = "unknown"
_FALLBACK_CONFIDENCE = 0.0


async def interpret_semantics(  # noqa: UP047
    schema_name: str,
    schema_type: type[SchemaT],
    prompt_identifier: str,
    prompt_manager: PromptManager,
    llm_provider: LLMProvider,
    render_context: PromptRenderContext,
    user_message: str,
    correlation_id: str | None,
    conversation_id: str | None,
    user_id: str | None,
) -> tuple[SchemaT, str]:
    """Render prompt_identifier, request structured output shaped like schema_type from the one
    LLM call every Agent already made, and return (interpretation, diagnostic).

    schema_type must be a SemanticInterpretation subclass (or structurally compatible: an
    `intent: str` and `intent_confidence: float` required field, everything else defaulted) so
    the safe-fallback constructor call below always succeeds."""
    try:
        rendered_prompt = await prompt_manager.render(prompt_identifier, render_context)
    except PromptError:
        return _empty(schema_type), ""

    prompt_diagnostic = f"[prompt={rendered_prompt.identifier}@{rendered_prompt.metadata.version}]"

    try:
        llm_response = await llm_provider.generate(
            LLMRequest(
                messages=[
                    LLMMessage(role=LLMMessageRole.SYSTEM, content=rendered_prompt.text),
                    LLMMessage(role=LLMMessageRole.USER, content=user_message),
                ],
                settings=LLMGenerationSettings(),
                response_schema=LLMResponseSchema(
                    name=schema_name, schema=schema_type.model_json_schema()
                ),
                correlation_id=correlation_id,
                conversation_id=conversation_id,
                user_id=user_id,
            )
        )
    except LLMError:
        return _empty(schema_type), prompt_diagnostic

    diagnostic = f"{prompt_diagnostic} [llm={llm_response.model}]"

    try:
        interpretation = schema_type.model_validate_json(llm_response.text)
    except (ValidationError, ValueError):
        logger.warning(
            "semantic_interpreter: model output for schema=%r did not conform; using the safe "
            "empty fallback interpretation instead.",
            schema_name,
        )
        return _empty(schema_type), diagnostic

    return interpretation, diagnostic


def _empty(schema_type: type[SchemaT]) -> SchemaT:  # noqa: UP047
    return schema_type(intent=_FALLBACK_INTENT, intent_confidence=_FALLBACK_CONFIDENCE)

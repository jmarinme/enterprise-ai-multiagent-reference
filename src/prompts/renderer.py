"""Deterministic, safe template rendering for prompts.

No eval(), no arbitrary Python execution, no third-party templating engine, and no use of
str.format()'s mini-language (which has its own attribute-access injection footguns). Variable
substitution is a controlled regex scan over a fixed, known set of placeholder names.
"""

from __future__ import annotations

import re

from src.prompts.exceptions import PromptRenderError
from src.prompts.models import PromptDefinition, PromptRenderContext

_PLACEHOLDER_PATTERN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def _known_variables(context: PromptRenderContext) -> dict[str, str | None]:
    return {
        "conversationId": context.conversation_id,
        "userId": context.user_id,
        "intent": context.intent,
        "conversationSummary": context.conversation_summary,
        "toolSummaries": "; ".join(context.tool_summaries) if context.tool_summaries else None,
        "agentName": context.agent_name,
        "retrievedKnowledge": (
            "; ".join(context.retrieved_knowledge) if context.retrieved_knowledge else None
        ),
    }


def render_template(definition: PromptDefinition, context: PromptRenderContext) -> str:
    """Render definition.template against context.

    Deterministic: the same definition and context always produce the same output or the same
    typed failure. Raises PromptRenderError for any placeholder outside the known variable set,
    or for a known placeholder declared in required_variables whose value is missing.
    """
    available = _known_variables(context)
    required = set(definition.metadata.required_variables)

    def _substitute(match: re.Match[str]) -> str:
        token = match.group(1)
        if token not in available:
            raise PromptRenderError(
                definition.metadata.identifier,
                f"Unknown template variable '{{{token}}}'",
            )
        value = available[token]
        if value is None:
            if token in required:
                raise PromptRenderError(
                    definition.metadata.identifier,
                    f"Missing required variable '{token}'",
                )
            return ""
        return value

    return _PLACEHOLDER_PATTERN.sub(_substitute, definition.template)

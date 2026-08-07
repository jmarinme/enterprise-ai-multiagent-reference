"""Unit tests for render_template: rendering, missing required variables, unexpected
variables, and determinism. No eval(), no arbitrary code execution.
"""

import pytest

from src.prompts.exceptions import PromptRenderError
from src.prompts.models import PromptDefinition, PromptMetadata, PromptRenderContext, PromptVersion
from src.prompts.renderer import render_template


def _definition(template: str, required_variables: list[str] | None = None) -> PromptDefinition:
    return PromptDefinition(
        metadata=PromptMetadata(
            identifier="test.prompt",
            version=PromptVersion(major=1, minor=0, patch=0),
            purpose="test",
            required_variables=required_variables or [],
        ),
        template=template,
    )


async def test_renders_all_known_variables() -> None:
    definition = _definition(
        "conv={conversationId} user={userId} intent={intent} "
        "summary={conversationSummary} tools={toolSummaries} agent={agentName}"
    )
    context = PromptRenderContext(
        conversation_id="conv-1",
        user_id="user-1",
        intent="CLAIMS",
        conversation_summary="a summary",
        tool_summaries=["tool result A", "tool result B"],
        agent_name="ClaimsAgent",
    )

    rendered = render_template(definition, context)

    assert rendered == (
        "conv=conv-1 user=user-1 intent=CLAIMS summary=a summary "
        "tools=tool result A; tool result B agent=ClaimsAgent"
    )


async def test_optional_missing_variable_renders_as_empty_string() -> None:
    definition = _definition("summary=[{conversationSummary}]")
    context = PromptRenderContext()

    rendered = render_template(definition, context)

    assert rendered == "summary=[]"


async def test_missing_required_variable_raises_prompt_render_error() -> None:
    definition = _definition("agent={agentName}", required_variables=["agentName"])
    context = PromptRenderContext(agent_name=None)

    with pytest.raises(PromptRenderError):
        render_template(definition, context)


async def test_unexpected_variable_raises_prompt_render_error() -> None:
    definition = _definition("value={somethingNotSupported}")
    context = PromptRenderContext()

    with pytest.raises(PromptRenderError):
        render_template(definition, context)


async def test_rendering_is_deterministic_across_repeated_calls() -> None:
    definition = _definition("agent={agentName}", required_variables=["agentName"])
    context = PromptRenderContext(agent_name="ClaimsAgent")

    first = render_template(definition, context)
    second = render_template(definition, context)

    assert first == second == "agent=ClaimsAgent"


async def test_template_with_no_placeholders_renders_unchanged() -> None:
    definition = _definition("Plain text with no variables at all.")

    rendered = render_template(definition, PromptRenderContext())

    assert rendered == "Plain text with no variables at all."

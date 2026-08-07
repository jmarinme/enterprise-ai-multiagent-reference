"""Unit tests for the shared annotate_with_prompt_and_llm helper (extracted from
ClaimsAgent/BrokerAgent in PBI-01-07): success annotation, and graceful degradation when
PromptManager or LLMProvider fails.
"""

from pathlib import Path

from src.agents.shared.annotation import annotate_with_prompt_and_llm
from src.llm.exceptions import LLMProviderError
from src.llm.mock_provider import MockLLMProvider
from src.llm.models import LLMRequest, LLMResponse
from src.prompts.exceptions import PromptNotFoundError
from src.prompts.filesystem_provider import FileSystemPromptProvider
from src.prompts.manager import PromptManager
from src.prompts.models import PromptRenderContext, RenderedPrompt


def _build_prompt_manager() -> PromptManager:
    return PromptManager(provider=FileSystemPromptProvider(prompts_root=Path("configs/prompts")))


class _RaisingPromptManager:
    async def render(self, identifier: str, context: PromptRenderContext) -> RenderedPrompt:
        raise PromptNotFoundError(identifier)


class _RaisingLLMProvider:
    async def generate(self, request: LLMRequest) -> LLMResponse:
        raise LLMProviderError("stub", "simulated outage")


async def test_appends_prompt_and_llm_annotations_on_success() -> None:
    result = await annotate_with_prompt_and_llm(
        response_text="base text",
        prompt_identifier="claims.system",
        prompt_manager=_build_prompt_manager(),
        llm_provider=MockLLMProvider(),
        render_context=PromptRenderContext(agent_name="TestAgent"),
        user_message="hello",
        correlation_id=None,
        conversation_id="conv-1",
        user_id="user-1",
    )

    assert result.startswith("base text ")
    assert "[prompt=claims.system@" in result
    assert "[llm=mock-llm]" in result


async def test_degrades_to_base_text_when_prompt_manager_fails() -> None:
    result = await annotate_with_prompt_and_llm(
        response_text="base text",
        prompt_identifier="claims.system",
        prompt_manager=_RaisingPromptManager(),  # type: ignore[arg-type]
        llm_provider=MockLLMProvider(),
        render_context=PromptRenderContext(agent_name="TestAgent"),
        user_message="hello",
        correlation_id=None,
        conversation_id="conv-1",
        user_id="user-1",
    )

    assert result == "base text"


async def test_degrades_to_prompt_annotation_only_when_llm_provider_fails() -> None:
    result = await annotate_with_prompt_and_llm(
        response_text="base text",
        prompt_identifier="claims.system",
        prompt_manager=_build_prompt_manager(),
        llm_provider=_RaisingLLMProvider(),
        render_context=PromptRenderContext(agent_name="TestAgent"),
        user_message="hello",
        correlation_id=None,
        conversation_id="conv-1",
        user_id="user-1",
    )

    assert "[prompt=claims.system@" in result
    assert "[llm=" not in result

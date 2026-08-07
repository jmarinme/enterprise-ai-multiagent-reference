"""Unit tests specifically for ClaimsAgent's LLMProvider injection (PBI-01-04): the agent
depends on LLMProvider (never a concrete provider), and its response is deterministic when
MockLLMProvider (the default local provider) is active.
"""

from pathlib import Path

from src.agents.claims_agent import ClaimsAgent
from src.llm.mock_provider import MockLLMProvider
from src.prompts.filesystem_provider import FileSystemPromptProvider
from src.prompts.manager import PromptManager
from src.services.tools.claims_status_tool import ClaimsStatusTool
from src.supervisor.models import AgentRequest, ConversationContext
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry


def _build_agent() -> ClaimsAgent:
    tool_registry = InMemoryToolRegistry()
    tool_registry.register(ClaimsStatusTool())
    prompt_manager = PromptManager(
        provider=FileSystemPromptProvider(prompts_root=Path("configs/prompts"))
    )
    return ClaimsAgent(
        tool_executor=ToolExecutor(tool_registry=tool_registry),
        prompt_manager=prompt_manager,
        llm_provider=MockLLMProvider(),
    )


async def test_claims_agent_response_includes_the_mock_llm_output() -> None:
    agent = _build_agent()
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    response = await agent.handle(
        AgentRequest(message="claim status please", user_id="user-1"), context
    )

    assert "deterministic mock LLM response" in response.response


async def test_claims_agent_response_is_fully_deterministic_with_mock_provider() -> None:
    agent = _build_agent()
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    first = await agent.handle(
        AgentRequest(message="claim status please", user_id="user-1"), context
    )
    second = await agent.handle(
        AgentRequest(message="claim status please", user_id="user-1"), context
    )

    assert first.response == second.response

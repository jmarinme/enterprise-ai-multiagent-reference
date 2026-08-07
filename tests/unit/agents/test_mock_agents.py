"""Unit tests for the four deterministic mock agents. No insurance logic, no Azure OpenAI."""

from collections.abc import Callable
from pathlib import Path

import pytest

from src.agents.broker_agent import BrokerAgent
from src.agents.claims_agent import ClaimsAgent
from src.agents.commercial_intake_agent import CommercialIntakeAgent
from src.agents.fallback_agent import FallbackAgent
from src.llm.mock_provider import MockLLMProvider
from src.prompts.filesystem_provider import FileSystemPromptProvider
from src.prompts.manager import PromptManager
from src.rag.local_provider import LocalKnowledgeProvider
from src.rag.retriever import KnowledgeRetriever
from src.services.tools.policy_lookup_tool import PolicyLookupTool
from src.supervisor.models import AgentRequest, ConversationContext, IntentCategory
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry


def _build_claims_agent() -> ClaimsAgent:
    tool_registry = InMemoryToolRegistry()
    tool_registry.register(PolicyLookupTool())
    prompt_manager = PromptManager(
        provider=FileSystemPromptProvider(prompts_root=Path("configs/prompts"))
    )
    knowledge_retriever = KnowledgeRetriever(
        provider=LocalKnowledgeProvider(documents_root=Path("configs/knowledge_base"))
    )
    return ClaimsAgent(
        tool_executor=ToolExecutor(tool_registry=tool_registry),
        prompt_manager=prompt_manager,
        llm_provider=MockLLMProvider(),
        knowledge_retriever=knowledge_retriever,
    )


def _build_broker_agent() -> BrokerAgent:
    tool_registry = InMemoryToolRegistry()
    tool_registry.register(PolicyLookupTool())
    prompt_manager = PromptManager(
        provider=FileSystemPromptProvider(prompts_root=Path("configs/prompts"))
    )
    return BrokerAgent(
        tool_executor=ToolExecutor(tool_registry=tool_registry),
        prompt_manager=prompt_manager,
        llm_provider=MockLLMProvider(),
    )


def _build_commercial_intake_agent() -> CommercialIntakeAgent:
    tool_registry = InMemoryToolRegistry()
    tool_registry.register(PolicyLookupTool())
    prompt_manager = PromptManager(
        provider=FileSystemPromptProvider(prompts_root=Path("configs/prompts"))
    )
    return CommercialIntakeAgent(
        tool_executor=ToolExecutor(tool_registry=tool_registry),
        prompt_manager=prompt_manager,
        llm_provider=MockLLMProvider(),
    )


@pytest.mark.parametrize(
    ("agent_factory", "expected_name", "expected_intent"),
    [
        (_build_claims_agent, "ClaimsAgent", IntentCategory.CLAIMS),
        (_build_broker_agent, "BrokerAgent", IntentCategory.BROKER),
        (_build_commercial_intake_agent, "CommercialIntakeAgent", IntentCategory.COMMERCIAL),
        (FallbackAgent, "FallbackAgent", IntentCategory.UNKNOWN),
    ],
)
async def test_agent_returns_deterministic_response(
    agent_factory: Callable[[], object], expected_name: str, expected_intent: IntentCategory
) -> None:
    agent = agent_factory()
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")
    request = AgentRequest(message="anything", user_id="user-1", conversation_id="conv-1")

    response = await agent.handle(request=request, context=context)  # type: ignore[attr-defined]

    assert agent.name == expected_name  # type: ignore[attr-defined]
    assert response.agent == expected_name
    assert response.intent == expected_intent
    assert response.conversation_id == "conv-1"
    assert isinstance(response.response, str)
    assert len(response.response) > 0


async def test_agent_response_is_stable_when_input_has_no_recognizable_claims_fields() -> None:
    """As of PBI-01-05, ClaimsAgent's business-fact text is fully deterministic (derived from
    Tool/state-machine results, never LLM wording — see
    tests/unit/agents/test_claims_agent_llm_integration.py). Two different first messages that
    neither one contains a recognizable field, nor any keyword the PBI-02-01 knowledge base
    would match (a genuine, expected new source of input-dependence — see
    docs/sprint_02/decisions.md), both simply prompt for the same first missing field, so the
    full response is identical, not just its agent/intent identity."""
    agent = _build_claims_agent()
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    first = await agent.handle(
        AgentRequest(message="banana kayak umbrella", user_id="user-1"), context
    )
    second = await agent.handle(
        AgentRequest(message="zebra trombone lighthouse", user_id="user-1"), context
    )

    assert first.agent == second.agent == "ClaimsAgent"
    assert first.intent == second.intent
    assert first.response == second.response
    assert "[prompt=claims.system@3.0.0]" in first.response

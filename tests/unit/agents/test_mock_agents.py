"""Unit tests for the four deterministic mock agents. No insurance logic, no Azure OpenAI."""

from collections.abc import Callable

import pytest

from src.agents.broker_agent import BrokerAgent
from src.agents.claims_agent import ClaimsAgent
from src.agents.commercial_intake_agent import CommercialIntakeAgent
from src.agents.fallback_agent import FallbackAgent
from src.services.tools.claims_status_tool import ClaimsStatusTool
from src.supervisor.models import AgentRequest, ConversationContext, IntentCategory
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry


def _build_claims_agent() -> ClaimsAgent:
    tool_registry = InMemoryToolRegistry()
    tool_registry.register(ClaimsStatusTool())
    return ClaimsAgent(tool_executor=ToolExecutor(tool_registry=tool_registry))


@pytest.mark.parametrize(
    ("agent_factory", "expected_name", "expected_intent"),
    [
        (_build_claims_agent, "ClaimsAgent", IntentCategory.CLAIMS),
        (BrokerAgent, "BrokerAgent", IntentCategory.BROKER),
        (CommercialIntakeAgent, "CommercialIntakeAgent", IntentCategory.COMMERCIAL),
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


async def test_agent_response_is_identical_regardless_of_input_message() -> None:
    agent = _build_claims_agent()
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    first = await agent.handle(
        AgentRequest(message="first message", user_id="user-1"), context
    )
    second = await agent.handle(
        AgentRequest(message="completely different message", user_id="user-1"), context
    )

    assert first.response == second.response

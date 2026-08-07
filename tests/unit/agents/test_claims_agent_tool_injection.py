"""Unit tests specifically for ClaimsAgent's ToolExecutor injection (PBI-01-02): the agent
depends on ToolExecutor, never a concrete Tool, and degrades gracefully when the tool fails.
"""

from src.agents.claims_agent import ClaimsAgent
from src.services.tools.claims_status_tool import ClaimsStatusTool
from src.supervisor.models import AgentRequest, ConversationContext
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry


async def test_claims_agent_includes_synthetic_tool_result_in_its_response() -> None:
    registry = InMemoryToolRegistry()
    registry.register(ClaimsStatusTool())
    agent = ClaimsAgent(tool_executor=ToolExecutor(tool_registry=registry))
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    response = await agent.handle(
        AgentRequest(message="claim status please", user_id="user-1"), context
    )

    assert "synthetic claim lookup" in response.response
    assert "under_review" in response.response


async def test_claims_agent_degrades_gracefully_when_the_tool_is_not_registered() -> None:
    empty_registry = InMemoryToolRegistry()
    agent = ClaimsAgent(tool_executor=ToolExecutor(tool_registry=empty_registry))
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    response = await agent.handle(
        AgentRequest(message="claim status please", user_id="user-1"), context
    )

    assert "synthetic claim lookup unavailable" in response.response
    assert response.agent == "ClaimsAgent"

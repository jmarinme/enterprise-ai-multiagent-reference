"""Mock Broker Services Agent. Deterministic response only — validates the orchestration
architecture. No insurance logic, no Azure OpenAI, no RAG.
Implements the Agent Protocol (src.supervisor.registry).
"""

from __future__ import annotations

from src.supervisor.models import AgentRequest, AgentResponse, ConversationContext, IntentCategory


class BrokerAgent:
    """Deterministic mock agent registered for the BROKER intent."""

    name = "BrokerAgent"

    async def handle(self, request: AgentRequest, context: ConversationContext) -> AgentResponse:
        return AgentResponse(
            conversation_id=context.conversation_id,
            agent=self.name,
            intent=IntentCategory.BROKER,
            response=(
                "This is a mock Broker Services Agent response. Broker business logic is not "
                "implemented in this PBI."
            ),
        )

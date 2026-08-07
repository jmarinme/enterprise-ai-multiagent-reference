"""Mock Commercial Intake Agent. Deterministic response only — validates the orchestration
architecture. No insurance logic, no Azure OpenAI, no RAG.
Implements the Agent Protocol (src.supervisor.registry).
"""

from __future__ import annotations

from src.supervisor.models import AgentRequest, AgentResponse, ConversationContext, IntentCategory


class CommercialIntakeAgent:
    """Deterministic mock agent registered for the COMMERCIAL intent."""

    name = "CommercialIntakeAgent"

    async def handle(self, request: AgentRequest, context: ConversationContext) -> AgentResponse:
        return AgentResponse(
            conversation_id=context.conversation_id,
            agent=self.name,
            intent=IntentCategory.COMMERCIAL,
            response=(
                "This is a mock Commercial Intake Agent response. Commercial intake business "
                "logic is not implemented in this PBI."
            ),
        )

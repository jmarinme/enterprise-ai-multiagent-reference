"""Mock Fallback Agent, registered for the UNKNOWN intent.

Not one of the three agents explicitly requested for PBI-01-01 — added so the AgentRegistry
has a deterministic entry for every IntentCategory the rule-based resolver can produce,
keeping the Supervisor's routing fully registry-driven (no special-casing "no agent found"
for UNKNOWN specifically). Deterministic response only, same as the other mock agents.
"""

from __future__ import annotations

from src.supervisor.models import AgentRequest, AgentResponse, ConversationContext, IntentCategory


class FallbackAgent:
    """Deterministic mock agent registered for the UNKNOWN intent."""

    name = "FallbackAgent"

    async def handle(self, request: AgentRequest, context: ConversationContext) -> AgentResponse:
        return AgentResponse(
            conversation_id=context.conversation_id,
            agent=self.name,
            intent=IntentCategory.UNKNOWN,
            response=(
                "I could not determine how to help with that. A human may need to assist you."
            ),
        )

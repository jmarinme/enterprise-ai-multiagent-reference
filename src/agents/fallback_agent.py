"""Mock Fallback Agent, registered for the UNKNOWN intent.

Not one of the three agents explicitly requested for PBI-01-01 — added so the AgentRegistry
has a deterministic entry for every IntentCategory the rule-based resolver can produce,
keeping the Supervisor's routing fully registry-driven (no special-casing "no agent found"
for UNKNOWN specifically). Deterministic response only, same as the other mock agents.
"""

from __future__ import annotations

from src.agents.shared.language import LANGUAGE_METADATA_KEY, resolve_language
from src.core.tool_calling.models import ReActEventSink
from src.supervisor.models import AgentRequest, AgentResponse, ConversationContext, IntentCategory

_MESSAGES = {
    "es-MX": "No pude identificar cómo ayudarte con eso. Es posible que una persona deba asistirte.",
    "en": "I could not determine how to help with that. A human may need to assist you.",
}


class FallbackAgent:
    """Deterministic mock agent registered for the UNKNOWN intent."""

    name = "FallbackAgent"

    async def handle(
        self,
        request: AgentRequest,
        context: ConversationContext,
        on_react_event: ReActEventSink | None = None,
    ) -> AgentResponse:
        del on_react_event  # No LLM/Tool Calling loop here — nothing to observe.
        language = resolve_language(context.metadata, request.message)
        return AgentResponse(
            conversation_id=context.conversation_id,
            agent=self.name,
            intent=IntentCategory.UNKNOWN,
            response=_MESSAGES[language],
            metadata={LANGUAGE_METADATA_KEY: language},
        )

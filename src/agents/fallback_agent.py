"""Mock Fallback Agent, registered for the UNKNOWN intent.

Not one of the three agents explicitly requested for PBI-01-01 — added so the AgentRegistry
has a deterministic entry for every IntentCategory the rule-based resolver can produce,
keeping the Supervisor's routing fully registry-driven (no special-casing "no agent found"
for UNKNOWN specifically). Deterministic response only, same as the other mock agents.

PBI-14-04: also handles the genuine-ambiguity case (turn_interpretation.requires_clarification)
— when the shared semantic turn interpretation could not confidently distinguish between two of
the three business domains, this Agent asks a short, deterministic, TEMPLATED clarification
question naming those two domains, instead of the generic "I could not determine how to help"
message. The clarification TEXT is never LLM-authored free prose (CLAUDE.md architecture
principle #2 — business-facing response text stays deterministic); the LLM only ever supplied
which two intents are plausible (turn_interpretation.alternative_intents), never the wording.
"""

from __future__ import annotations

from src.agents.shared.language import LANGUAGE_METADATA_KEY, Language, resolve_language
from src.agents.shared.semantic_models import (
    TURN_INTENT_BROKER,
    TURN_INTENT_CLAIMS,
    TURN_INTENT_COMMERCIAL,
    TurnInterpretation,
)
from src.core.tool_calling.models import ReActEventSink
from src.supervisor.models import AgentRequest, AgentResponse, ConversationContext, IntentCategory

_MESSAGES = {
    "es-MX": "No pude identificar cómo ayudarte con eso. Es posible que una persona deba asistirte.",
    "en": "I could not determine how to help with that. A human may need to assist you.",
}

# One deterministic, bilingual clarification template per unordered pair of business domains —
# never LLM-authored (see module docstring). Keyed by a frozenset of the two wire-level intent
# strings (src.agents.shared.semantic_models) turn_interpretation.alternative_intents/intent
# named as plausible.
_CLARIFICATION_MESSAGES: dict[frozenset[str], dict[Language, str]] = {
    frozenset({TURN_INTENT_CLAIMS, TURN_INTENT_BROKER}): {
        "es-MX": "¿Te refieres a reportar un siniestro, o a una consulta sobre tu póliza o comisión?",
        "en": "Are you reporting a claim, or asking about an existing policy or commission?",
    },
    frozenset({TURN_INTENT_CLAIMS, TURN_INTENT_COMMERCIAL}): {
        "es-MX": "¿Quieres reportar un siniestro existente, o asegurar/cotizar algo nuevo?",
        "en": "Do you want to report an existing claim, or insure/quote something new?",
    },
    frozenset({TURN_INTENT_BROKER, TURN_INTENT_COMMERCIAL}): {
        "es-MX": (
            "¿Quieres revisar una póliza o comisión existente, o cotizar protección para un "
            "nuevo negocio?"
        ),
        "en": (
            "Would you like to review an existing policy or commission, or get coverage for a "
            "new business?"
        ),
    },
}
_GENERIC_CLARIFICATION = {
    "es-MX": (
        "¿Podrías darme un poco más de detalle? Por ejemplo: reportar un siniestro, revisar tu "
        "póliza o comisiones, o asegurar algo nuevo."
    ),
    "en": (
        "Could you give me a bit more detail? For example: report a claim, review your policy "
        "or commissions, or insure something new."
    ),
}


def _clarification_message(turn_interpretation: TurnInterpretation, language: Language) -> str:
    candidates = {turn_interpretation.intent, *(a.intent for a in turn_interpretation.alternative_intents)}
    candidates.discard("unknown")
    if len(candidates) == 2:
        template = _CLARIFICATION_MESSAGES.get(frozenset(candidates))
        if template is not None:
            return template.get(language) or template["es-MX"]
    return _GENERIC_CLARIFICATION.get(language) or _GENERIC_CLARIFICATION["es-MX"]


class FallbackAgent:
    """Deterministic mock agent registered for the UNKNOWN intent."""

    name = "FallbackAgent"

    async def handle(
        self,
        request: AgentRequest,
        context: ConversationContext,
        on_react_event: ReActEventSink | None = None,
        turn_interpretation: TurnInterpretation | None = None,
        turn_interpretation_diagnostic: str = "",
    ) -> AgentResponse:
        del on_react_event, turn_interpretation_diagnostic  # Nothing to observe or annotate here.
        language = resolve_language(context.metadata, request.message)
        response_text = _MESSAGES[language]
        if turn_interpretation is not None and turn_interpretation.requires_clarification:
            response_text = _clarification_message(turn_interpretation, language)
        return AgentResponse(
            conversation_id=context.conversation_id,
            agent=self.name,
            intent=IntentCategory.UNKNOWN,
            response=response_text,
            metadata={LANGUAGE_METADATA_KEY: language},
        )

"""Unit tests for FallbackAgent (PBI-14-04): the plain "no idea" message vs. the deterministic,
TEMPLATED clarification message for a genuine cross-domain ambiguity — never LLM-authored prose.
"""

from src.agents.fallback_agent import FallbackAgent
from src.agents.shared.semantic_models import AlternativeIntent, TurnInterpretation
from src.supervisor.models import AgentRequest, ConversationContext, IntentCategory


async def test_plain_unknown_message_when_no_turn_interpretation_is_given() -> None:
    agent = FallbackAgent()
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    response = await agent.handle(
        AgentRequest(message="hola", user_id="user-1"), context
    )

    assert response.agent == "FallbackAgent"
    assert response.intent == IntentCategory.UNKNOWN
    assert "no pude identificar" in response.response.lower()


async def test_plain_unknown_message_when_clarification_not_required() -> None:
    agent = FallbackAgent()
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")
    turn = TurnInterpretation(intent="unknown", intent_confidence=0.9, requires_clarification=False)

    response = await agent.handle(
        AgentRequest(message="cuéntame un chiste", user_id="user-1"),
        context,
        turn_interpretation=turn,
    )

    assert "no pude identificar" in response.response.lower()


async def test_clarification_message_for_broker_vs_commercial_ambiguity() -> None:
    agent = FallbackAgent()
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")
    turn = TurnInterpretation(
        intent="broker_services",
        intent_confidence=0.55,
        requires_clarification=True,
        alternative_intents=[AlternativeIntent(intent="commercial_intake", confidence=0.5)],
    )

    response = await agent.handle(
        AgentRequest(message="quiero revisar lo de mi negocio", user_id="user-1"),
        context,
        turn_interpretation=turn,
    )

    lowered = response.response.lower()
    assert "póliza" in lowered or "comisión" in lowered
    assert "nuevo negocio" in lowered


async def test_clarification_message_for_claims_vs_commercial_ambiguity() -> None:
    agent = FallbackAgent()
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")
    turn = TurnInterpretation(
        intent="claims",
        intent_confidence=0.5,
        requires_clarification=True,
        alternative_intents=[AlternativeIntent(intent="commercial_intake", confidence=0.5)],
    )

    response = await agent.handle(
        AgentRequest(message="lo de mi fábrica", user_id="user-1"),
        context,
        turn_interpretation=turn,
    )

    lowered = response.response.lower()
    assert "siniestro" in lowered
    assert "asegurar" in lowered or "cotizar" in lowered


async def test_clarification_falls_back_to_generic_message_without_a_clear_pair() -> None:
    agent = FallbackAgent()
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")
    turn = TurnInterpretation(intent="unknown", intent_confidence=0.3, requires_clarification=True)

    response = await agent.handle(
        AgentRequest(message="algo confuso", user_id="user-1"),
        context,
        turn_interpretation=turn,
    )

    assert "siniestro" in response.response.lower()
    assert "comisiones" in response.response.lower()


async def test_clarification_message_is_never_llm_authored_free_text() -> None:
    """The clarification wording must come only from the fixed template catalog — never from
    turn_interpretation.routing_reason or any other model-authored field."""
    agent = FallbackAgent()
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")
    turn = TurnInterpretation(
        intent="broker_services",
        intent_confidence=0.55,
        requires_clarification=True,
        routing_reason="This text must never leak into the user-facing response.",
        alternative_intents=[AlternativeIntent(intent="commercial_intake", confidence=0.5)],
    )

    response = await agent.handle(
        AgentRequest(message="algo", user_id="user-1"), context, turn_interpretation=turn
    )

    assert "must never leak" not in response.response

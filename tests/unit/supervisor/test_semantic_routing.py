"""Unit tests for src.supervisor.semantic_routing.resolve_turn (PBI-14-04): the deterministic
routing-decision logic applied to one structured TurnInterpretation, and the resilience
fallback to RuleBasedIntentResolver when the semantic call itself degrades.
"""

from pathlib import Path

from src.llm.exceptions import LLMProviderError
from src.llm.mock_provider import MockLLMProvider
from src.llm.models import LLMRequest, LLMResponse
from src.prompts.filesystem_provider import FileSystemPromptProvider
from src.prompts.manager import PromptManager
from src.supervisor.intent import RuleBasedIntentResolver
from src.supervisor.models import ConversationContext, IntentCategory
from src.supervisor.semantic_routing import (
    ROUTING_SOURCE_CLARIFICATION,
    ROUTING_SOURCE_DETERMINISTIC_FALLBACK,
    ROUTING_SOURCE_SEMANTIC,
    SemanticRoutingConfig,
    resolve_turn,
)

_SCHEMA_NAME = "turn_interpretation"


def _build_prompt_manager() -> PromptManager:
    return PromptManager(provider=FileSystemPromptProvider(prompts_root=Path("configs/prompts")))


def _context(current_agent: str | None = None) -> ConversationContext:
    return ConversationContext(
        conversation_id="conv-1", user_id="user-1", current_agent=current_agent
    )


def _turn_json(
    intent: str,
    confidence: float,
    *,
    requires_clarification: bool = False,
    alternatives: list[tuple[str, float]] | None = None,
) -> str:
    alt_json = ", ".join(f'{{"intent": "{i}", "confidence": {c}}}' for i, c in (alternatives or []))
    return (
        f'{{"intent": "{intent}", "intent_confidence": {confidence}, '
        f'"requires_clarification": {"true" if requires_clarification else "false"}, '
        f'"alternative_intents": [{alt_json}]}}'
    )


class _RaisingLLMProvider:
    async def generate(self, request: LLMRequest) -> LLMResponse:
        raise LLMProviderError("stub", "simulated outage")

    async def health_check(self) -> bool:
        return False


async def test_high_confidence_claims_routes_semantically() -> None:
    llm_provider = MockLLMProvider(
        structured_response_plan={_SCHEMA_NAME: _turn_json("claims", 0.95)}
    )

    decision = await resolve_turn(
        message="un camión me pegó por atrás",
        context=_context(),
        prompt_manager=_build_prompt_manager(),
        llm_provider=llm_provider,
        correlation_id=None,
        user_id="user-1",
        config=SemanticRoutingConfig(),
        rule_based_resolver=RuleBasedIntentResolver(),
    )

    assert decision.category == IntentCategory.CLAIMS
    assert decision.routing_source == ROUTING_SOURCE_SEMANTIC
    assert decision.requires_clarification is False


async def test_high_confidence_broker_routes_semantically() -> None:
    llm_provider = MockLLMProvider(
        structured_response_plan={_SCHEMA_NAME: _turn_json("broker_services", 0.9)}
    )

    decision = await resolve_turn(
        message="¿ya me pagaron?",
        context=_context(),
        prompt_manager=_build_prompt_manager(),
        llm_provider=llm_provider,
        correlation_id=None,
        user_id="user-1",
        config=SemanticRoutingConfig(),
        rule_based_resolver=RuleBasedIntentResolver(),
    )

    assert decision.category == IntentCategory.BROKER
    assert decision.routing_source == ROUTING_SOURCE_SEMANTIC


async def test_high_confidence_commercial_routes_semantically() -> None:
    llm_provider = MockLLMProvider(
        structured_response_plan={_SCHEMA_NAME: _turn_json("commercial_intake", 0.93)}
    )

    decision = await resolve_turn(
        message="quiero proteger mi fábrica",
        context=_context(),
        prompt_manager=_build_prompt_manager(),
        llm_provider=llm_provider,
        correlation_id=None,
        user_id="user-1",
        config=SemanticRoutingConfig(),
        rule_based_resolver=RuleBasedIntentResolver(),
    )

    assert decision.category == IntentCategory.COMMERCIAL
    assert decision.routing_source == ROUTING_SOURCE_SEMANTIC


async def test_medium_confidence_routes_when_keyword_resolver_corroborates() -> None:
    # "claim" is a genuine _CLAIMS_KEYWORDS entry — corroborates the medium-confidence guess.
    llm_provider = MockLLMProvider(
        structured_response_plan={_SCHEMA_NAME: _turn_json("claims", 0.5)}
    )

    decision = await resolve_turn(
        message="I need to file a claim",
        context=_context(),
        prompt_manager=_build_prompt_manager(),
        llm_provider=llm_provider,
        correlation_id=None,
        user_id="user-1",
        config=SemanticRoutingConfig(),
        rule_based_resolver=RuleBasedIntentResolver(),
    )

    assert decision.category == IntentCategory.CLAIMS
    assert decision.routing_source == ROUTING_SOURCE_SEMANTIC
    assert "corroborated" in decision.routing_reason


async def test_medium_confidence_without_corroboration_requires_clarification() -> None:
    llm_provider = MockLLMProvider(
        structured_response_plan={_SCHEMA_NAME: _turn_json("commercial_intake", 0.5)}
    )

    # Deliberately no _COMMERCIAL_KEYWORDS/_BROKER_KEYWORDS/_CLAIMS_KEYWORDS overlap, so the
    # keyword resolver has nothing to corroborate the medium-confidence semantic guess with.
    decision = await resolve_turn(
        message="quiero platicar sobre eso que hablamos",
        context=_context(),
        prompt_manager=_build_prompt_manager(),
        llm_provider=llm_provider,
        correlation_id=None,
        user_id="user-1",
        config=SemanticRoutingConfig(),
        rule_based_resolver=RuleBasedIntentResolver(),
    )

    assert decision.category == IntentCategory.UNKNOWN
    assert decision.routing_source == ROUTING_SOURCE_CLARIFICATION
    assert decision.requires_clarification is True


async def test_explicit_requires_clarification_flag_always_clarifies() -> None:
    llm_provider = MockLLMProvider(
        structured_response_plan={
            _SCHEMA_NAME: _turn_json(
                "broker_services",
                0.6,
                requires_clarification=True,
                alternatives=[("commercial_intake", 0.55)],
            )
        }
    )

    decision = await resolve_turn(
        message="quiero revisar lo de mi negocio",
        context=_context(),
        prompt_manager=_build_prompt_manager(),
        llm_provider=llm_provider,
        correlation_id=None,
        user_id="user-1",
        config=SemanticRoutingConfig(),
        rule_based_resolver=RuleBasedIntentResolver(),
    )

    assert decision.category == IntentCategory.UNKNOWN
    assert decision.requires_clarification is True
    assert decision.routing_source == ROUTING_SOURCE_CLARIFICATION
    assert [a.intent for a in decision.turn_interpretation.alternative_intents] == [
        "commercial_intake"
    ]


async def test_low_confidence_falls_back_to_keyword_resolver() -> None:
    llm_provider = MockLLMProvider(
        structured_response_plan={_SCHEMA_NAME: _turn_json("claims", 0.1)}
    )

    decision = await resolve_turn(
        message="I need to file a claim",
        context=_context(),
        prompt_manager=_build_prompt_manager(),
        llm_provider=llm_provider,
        correlation_id=None,
        user_id="user-1",
        config=SemanticRoutingConfig(),
        rule_based_resolver=RuleBasedIntentResolver(),
    )

    assert decision.category == IntentCategory.CLAIMS
    assert decision.routing_source == ROUTING_SOURCE_DETERMINISTIC_FALLBACK
    assert decision.routing_reason == "low_semantic_confidence"


async def test_unknown_intent_routes_to_fallback_without_clarification() -> None:
    llm_provider = MockLLMProvider(
        structured_response_plan={_SCHEMA_NAME: _turn_json("unknown", 0.9)}
    )

    decision = await resolve_turn(
        message="cuéntame un chiste",
        context=_context(),
        prompt_manager=_build_prompt_manager(),
        llm_provider=llm_provider,
        correlation_id=None,
        user_id="user-1",
        config=SemanticRoutingConfig(),
        rule_based_resolver=RuleBasedIntentResolver(),
    )

    assert decision.category == IntentCategory.UNKNOWN
    assert decision.requires_clarification is False
    assert decision.routing_source == ROUTING_SOURCE_SEMANTIC


async def test_semantic_service_unavailable_falls_back_to_rule_based_resolver() -> None:
    """interpret_semantics never raises — a genuine LLM failure degrades to a safe empty
    interpretation whose diagnostic never reached "[llm=...]" (see
    src.agents.shared.semantic_interpreter). resolve_turn must detect this and use
    RuleBasedIntentResolver, never silently claim semantic routing occurred."""
    decision = await resolve_turn(
        message="I need to file a claim",
        context=_context(),
        prompt_manager=_build_prompt_manager(),
        llm_provider=_RaisingLLMProvider(),
        correlation_id=None,
        user_id="user-1",
        config=SemanticRoutingConfig(),
        rule_based_resolver=RuleBasedIntentResolver(),
    )

    assert decision.category == IntentCategory.CLAIMS
    assert decision.routing_source == ROUTING_SOURCE_DETERMINISTIC_FALLBACK
    assert decision.routing_reason == "semantic_service_unavailable"


async def test_malformed_structured_output_falls_back_to_rule_based_resolver() -> None:
    llm_provider = MockLLMProvider(structured_response_plan={_SCHEMA_NAME: "not valid json"})

    decision = await resolve_turn(
        message="I need to file a claim",
        context=_context(),
        prompt_manager=_build_prompt_manager(),
        llm_provider=llm_provider,
        correlation_id=None,
        user_id="user-1",
        config=SemanticRoutingConfig(),
        rule_based_resolver=RuleBasedIntentResolver(),
    )

    assert decision.category == IntentCategory.CLAIMS
    assert decision.routing_source == ROUTING_SOURCE_DETERMINISTIC_FALLBACK

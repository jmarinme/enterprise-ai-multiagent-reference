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
    SEMANTIC_ERROR_PROVIDER,
    SEMANTIC_ERROR_SCHEMA_VALIDATION,
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
    # PBI-14-07: successful semantic routing must never be reported as a semantic failure.
    assert decision.semantic_call_succeeded is True
    assert decision.semantic_error_category is None


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
    # PBI-14-07: ambiguity is not a technical failure — the semantic call itself succeeded, it
    # just found two plausible intents. Must be distinguishable from a real provider/schema
    # failure in observability, even though both currently route through non-"semantic" sources.
    assert decision.semantic_call_succeeded is True
    assert decision.semantic_error_category is None


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
    # PBI-14-07: the critical case routing_source/routing_reason alone cannot disambiguate — the
    # semantic call SUCCEEDED here (it returned a real, if low-confidence, classification); only
    # the deterministic ROUTING choice fell back to keywords. Must never be reported the same way
    # as test_semantic_service_unavailable_falls_back_to_rule_based_resolver's genuine failure
    # below, even though both share routing_source=deterministic_fallback.
    assert decision.semantic_call_succeeded is True
    assert decision.semantic_error_category is None


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
    # PBI-14-07: a real technical failure (the LLM call itself raised) — must be reported as
    # such, distinguishable from the "succeeded but low confidence" case above.
    assert decision.semantic_call_succeeded is False
    assert decision.semantic_error_category == SEMANTIC_ERROR_PROVIDER


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
    # PBI-14-07: the completion arrived (unlike the provider-outage case above) but failed
    # schema validation — a distinct, correctly-classified failure category.
    assert decision.semantic_call_succeeded is False
    assert decision.semantic_error_category == SEMANTIC_ERROR_SCHEMA_VALIDATION


def test_classify_semantic_error_prompt_render_failure() -> None:
    """PBI-14-07: an empty diagnostic means the prompt never rendered (PromptError, caught
    before any LLM call) — a distinct category from a provider or schema-validation failure.
    Tested directly against the private classifier since resolve_turn's own prompt_identifier
    is fixed and always resolves successfully against the real prompts directory."""
    from src.supervisor.semantic_routing import SEMANTIC_ERROR_PROMPT, _classify_semantic_error

    assert _classify_semantic_error("") == SEMANTIC_ERROR_PROMPT


def test_classify_semantic_error_provider_failure() -> None:
    from src.supervisor.semantic_routing import _classify_semantic_error

    assert (
        _classify_semantic_error("[prompt=supervisor.turn_interpretation@1.0.0]")
        == SEMANTIC_ERROR_PROVIDER
    )


def test_classify_semantic_error_schema_validation_failure() -> None:
    from src.supervisor.semantic_routing import _classify_semantic_error

    assert (
        _classify_semantic_error(
            "[prompt=supervisor.turn_interpretation@1.0.0] [llm=gpt-5-mini]"
        )
        == SEMANTIC_ERROR_SCHEMA_VALIDATION
    )

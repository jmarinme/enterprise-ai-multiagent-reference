"""Semantic-first turn routing (PBI-14-04).

BEFORE this PBI (PBI-14-03's own arrangement): `RuleBasedIntentResolver`'s deterministic
keyword matching was the Supervisor's ONLY routing input, and semantic understanding only ran
*after* an Agent was already selected — a correctly-phrased-but-keyword-free message (e.g. "un
camión me pegó por atrás") never reached the specialist Agent whose own semantic layer would
have understood it; `RuleBasedIntentResolver` returned UNKNOWN, so it was routed to
FallbackAgent, which never calls an LLM at all.

AFTER: `resolve_turn` below runs the SAME one per-turn LLM call
(`src.agents.shared.semantic_interpreter.interpret_semantics`, unchanged, reused verbatim) once,
BEFORE routing, and applies fixed, deterministic Python conditionals to its structured output —
never "reasoning". `RuleBasedIntentResolver` is kept only as: (a) the resilience fallback when
the semantic call itself degrades (Prompt/LLM/parse failure), and (b) a corroboration signal for
a medium-confidence semantic result. It is no longer the normal, primary routing authority.

The resulting `TurnInterpretation` (see src.agents.shared.semantic_models) is handed to
`SupervisorOrchestrator`, which passes it — unchanged, not re-requested — into whichever
specialist Agent it selects (src.supervisor.orchestrator). No specialist Agent calls
interpret_semantics for the same user turn again; see ADR-0014.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.agents.shared.semantic_interpreter import interpret_semantics
from src.agents.shared.semantic_models import (
    TURN_INTENT_BROKER,
    TURN_INTENT_CLAIMS,
    TURN_INTENT_COMMERCIAL,
    TURN_INTENT_UNKNOWN,
    TurnInterpretation,
)
from src.llm.provider import LLMProvider
from src.prompts.manager import PromptManager
from src.prompts.models import PromptRenderContext
from src.supervisor.intent import IntentResolver
from src.supervisor.models import ConversationContext, IntentCategory

_SCHEMA_NAME = "turn_interpretation"
_PROMPT_IDENTIFIER = "supervisor.turn_interpretation"
_ROUTER_AGENT_NAME = "Semantic Router"

# Wire-level intent string (src.agents.shared.semantic_models) -> Supervisor's own routing enum.
# Anything not in this map (including the model's own "unknown") resolves to UNKNOWN.
_INTENT_STRING_TO_CATEGORY: dict[str, IntentCategory] = {
    TURN_INTENT_CLAIMS: IntentCategory.CLAIMS,
    TURN_INTENT_BROKER: IntentCategory.BROKER,
    TURN_INTENT_COMMERCIAL: IntentCategory.COMMERCIAL,
}

# Routing sources recorded for observability (PBI-14-04 section 20) — a real, honest description
# of which mechanism actually produced the routing decision, never a fabricated "semantic" label
# when the deterministic fallback fired.
ROUTING_SOURCE_SEMANTIC = "semantic"
ROUTING_SOURCE_DETERMINISTIC_FALLBACK = "deterministic_fallback"
ROUTING_SOURCE_CLARIFICATION = "clarification"

# Normalized semantic-failure categories for observability (PBI-14-07) — derived only from the
# diagnostic string src.agents.shared.semantic_interpreter.interpret_semantics already returns,
# without widening that function's shared return contract (it has 4 call sites: this module plus
# every specialist Agent's own backward-compat fallback path). This means auth/timeout/rate-limit
# failures cannot currently be told apart — all of them collapse to SEMANTIC_ERROR_PROVIDER — see
# docs/sprint_14/decisions.md (PBI-14-07) for why finer granularity was judged out of this PBI's
# surgical scope.
SEMANTIC_ERROR_PROMPT = "prompt_error"
SEMANTIC_ERROR_PROVIDER = "provider_error"
SEMANTIC_ERROR_SCHEMA_VALIDATION = "schema_validation_error"


@dataclass(frozen=True)
class SemanticRoutingConfig:
    """Confidence thresholds for semantic-first routing (PBI-14-04 section 8).

    These are operational STARTING values, not a statistical guarantee — chosen as reasonable
    defaults for a synthetic reference platform with no production traffic to calibrate against
    yet. A future PBI with real measured precision/recall data should revisit them explicitly.
    """

    high_confidence: float = 0.7
    low_confidence: float = 0.4


@dataclass(frozen=True)
class RoutingDecision:
    """The Supervisor's fully deterministic routing decision, derived from one
    TurnInterpretation plus (only when needed) one RuleBasedIntentResolver call — never from the
    LLM directly."""

    category: IntentCategory
    routing_source: str
    routing_reason: str
    requires_clarification: bool
    turn_interpretation: TurnInterpretation
    diagnostic: str
    # semantic_call_succeeded/semantic_error_category (PBI-14-07): set explicitly at every
    # return site below — never inferred after the fact from routing_source/routing_reason,
    # because "deterministic_fallback" alone is ambiguous (it also fires when the semantic call
    # SUCCEEDED but returned low confidence — see the final return in resolve_turn).
    semantic_call_succeeded: bool
    semantic_error_category: str | None


def _is_empty_sentinel(turn: TurnInterpretation) -> bool:
    """True only for the exact safe-empty TurnInterpretation
    src.agents.shared.semantic_interpreter._empty() constructs — every field at its Pydantic
    default except intent/intent_confidence. A genuine LLM response is always distinguishable
    from this: the shared prompt requires a routing_reason on every real classification, so a
    None routing_reason combined with the sentinel's exact unknown/0.0 intent is a reliable
    "this call never actually produced real data" signal."""
    return (
        turn.intent == TURN_INTENT_UNKNOWN
        and turn.intent_confidence == 0.0
        and turn.routing_reason is None
        and not turn.alternative_intents
        and turn.confirmation is None
        and not turn.corrections
        and not turn.already_answered
        and not turn.missing_information
        and turn.claims_entities is None
        and turn.broker_entities is None
        and turn.commercial_entities is None
    )


def _semantic_call_succeeded(diagnostic: str, turn: TurnInterpretation) -> bool:
    """interpret_semantics never raises — a Prompt/LLM failure degrades to the safe empty
    TurnInterpretation with a diagnostic that never reaches "[llm=...]" (see
    src.agents.shared.semantic_interpreter), but a malformed-JSON *parse* failure still gets a
    "[llm=...]" diagnostic (the completion itself arrived successfully) with that same empty
    interpretation — so the diagnostic check alone is not sufficient; a genuine "semantic
    classification failure" per PBI-14-04 section 17 must catch all three cases uniformly."""
    return "[llm=" in diagnostic and not _is_empty_sentinel(turn)


def _classify_semantic_error(diagnostic: str) -> str:
    """Normalizes WHY the semantic call failed (PBI-14-07), using only the diagnostic string
    already produced by interpret_semantics — no exception type is propagated past it. Only
    called when _semantic_call_succeeded() has already returned False for this same diagnostic.

    - diagnostic == "" -> the prompt itself never rendered (PromptError, caught before any LLM
      call was attempted).
    - "[prompt=...]" present, "[llm=...]" absent -> the LLM call itself raised (any LLMError
      subtype: config, provider, rate-limit, timeout, or content-safety — interpret_semantics
      collapses all of these into one generic catch, so no finer distinction is available here).
    - "[llm=...]" present -> the completion arrived but failed to validate against
      TurnInterpretation's schema.
    """
    if not diagnostic:
        return SEMANTIC_ERROR_PROMPT
    if "[llm=" not in diagnostic:
        return SEMANTIC_ERROR_PROVIDER
    return SEMANTIC_ERROR_SCHEMA_VALIDATION


async def resolve_turn(
    *,
    message: str,
    context: ConversationContext,
    prompt_manager: PromptManager,
    llm_provider: LLMProvider,
    correlation_id: str | None,
    user_id: str,
    config: SemanticRoutingConfig,
    rule_based_resolver: IntentResolver,
) -> RoutingDecision:
    """The ONE per-turn semantic call, plus deterministic routing rules applied to its
    structured output (PBI-14-04 section 6). The Supervisor calling this never "reasons" — it
    only evaluates a fixed set of Python conditionals against data the LLM produced."""
    turn_interpretation, diagnostic = await interpret_semantics(
        schema_name=_SCHEMA_NAME,
        schema_type=TurnInterpretation,
        prompt_identifier=_PROMPT_IDENTIFIER,
        prompt_manager=prompt_manager,
        llm_provider=llm_provider,
        render_context=PromptRenderContext(
            conversation_id=context.conversation_id,
            user_id=user_id,
            conversation_summary=context.summary,
            agent_name=_ROUTER_AGENT_NAME,
        ),
        user_message=message,
        correlation_id=correlation_id,
        conversation_id=context.conversation_id,
        user_id=user_id,
    )

    if not _semantic_call_succeeded(diagnostic, turn_interpretation):
        rule_intent = await rule_based_resolver.resolve(message)
        return RoutingDecision(
            category=rule_intent.category,
            routing_source=ROUTING_SOURCE_DETERMINISTIC_FALLBACK,
            routing_reason="semantic_service_unavailable",
            requires_clarification=False,
            turn_interpretation=turn_interpretation,
            diagnostic=diagnostic,
            semantic_call_succeeded=False,
            semantic_error_category=_classify_semantic_error(diagnostic),
        )

    if turn_interpretation.requires_clarification:
        return RoutingDecision(
            category=IntentCategory.UNKNOWN,
            routing_source=ROUTING_SOURCE_CLARIFICATION,
            routing_reason=turn_interpretation.routing_reason or "ambiguous_intent",
            requires_clarification=True,
            turn_interpretation=turn_interpretation,
            diagnostic=diagnostic,
            semantic_call_succeeded=True,
            semantic_error_category=None,
        )

    category = _INTENT_STRING_TO_CATEGORY.get(turn_interpretation.intent, IntentCategory.UNKNOWN)

    if category == IntentCategory.UNKNOWN:
        return RoutingDecision(
            category=IntentCategory.UNKNOWN,
            routing_source=ROUTING_SOURCE_SEMANTIC,
            routing_reason=turn_interpretation.routing_reason or "unsupported_request",
            requires_clarification=False,
            turn_interpretation=turn_interpretation,
            diagnostic=diagnostic,
            semantic_call_succeeded=True,
            semantic_error_category=None,
        )

    if turn_interpretation.intent_confidence >= config.high_confidence:
        return RoutingDecision(
            category=category,
            routing_source=ROUTING_SOURCE_SEMANTIC,
            routing_reason=(
                turn_interpretation.routing_reason or f"semantic_match:{turn_interpretation.intent}"
            ),
            requires_clarification=False,
            turn_interpretation=turn_interpretation,
            diagnostic=diagnostic,
            semantic_call_succeeded=True,
            semantic_error_category=None,
        )

    if turn_interpretation.intent_confidence >= config.low_confidence:
        # Medium confidence: route only if the deterministic keyword resolver corroborates the
        # same category — a cheap, fully deterministic "contextual evidence" check. Disagreement
        # (or no keyword match at all) is treated as genuine ambiguity, not silently guessed.
        rule_intent = await rule_based_resolver.resolve(message)
        if rule_intent.category == category:
            return RoutingDecision(
                category=category,
                routing_source=ROUTING_SOURCE_SEMANTIC,
                routing_reason=f"semantic_corroborated_by_keyword:{turn_interpretation.intent}",
                requires_clarification=False,
                turn_interpretation=turn_interpretation,
                diagnostic=diagnostic,
                semantic_call_succeeded=True,
                semantic_error_category=None,
            )
        return RoutingDecision(
            category=IntentCategory.UNKNOWN,
            routing_source=ROUTING_SOURCE_CLARIFICATION,
            routing_reason="medium_confidence_without_corroboration",
            requires_clarification=True,
            turn_interpretation=turn_interpretation,
            diagnostic=diagnostic,
            semantic_call_succeeded=True,
            semantic_error_category=None,
        )

    # Below low_confidence: the semantic call itself succeeded but is genuinely unsure — defer
    # to the deterministic keyword resolver as a safe fallback (section 8's "low confidence:
    # clarification or safe fallback"; a keyword match here is a stronger, more specific signal
    # than an unconfident semantic guess).
    rule_intent = await rule_based_resolver.resolve(message)
    return RoutingDecision(
        category=rule_intent.category,
        routing_source=ROUTING_SOURCE_DETERMINISTIC_FALLBACK,
        routing_reason="low_semantic_confidence",
        requires_clarification=False,
        turn_interpretation=turn_interpretation,
        diagnostic=diagnostic,
        semantic_call_succeeded=True,
        semantic_error_category=None,
    )

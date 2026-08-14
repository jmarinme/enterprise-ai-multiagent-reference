"""Concrete orchestration engine implementing the Supervisor Protocol.

Depends only on interfaces (ConversationRepository, IntentResolver, AgentRegistry, PromptManager,
LLMProvider) plus a typed SupervisorConfig — all injected through the constructor, no globals.
This class never imports or references any concrete Agent implementation; adding a new agent
never requires changing this file.

PBI-14-04: this Supervisor now owns the ONE per-turn semantic call (moved here from inside each
specialist Agent, see src.supervisor.semantic_routing and ADR-0014) so semantic understanding
runs BEFORE routing, not after it — the architectural gap that let a keyword-free message (e.g.
"un camión me pegó por atrás") get misrouted to FallbackAgent even though the specialist Agent's
own semantic layer would have understood it. PromptManager/LLMProvider are genuinely new
constructor dependencies (previously only Agents held them); this is still not "the Supervisor
reasoning" — src.supervisor.semantic_routing.resolve_turn applies only fixed, deterministic
Python conditionals to the LLM's structured output, exactly like RuleBasedIntentResolver already
applied fixed conditionals to keyword matches.

PBI-04-04 (performance requirement): each pipeline phase is timed and logged (never raised,
never blocking) via the standard library `logging` module — deliberately not
apps.api.src.observability (this is a reusable src/ module; apps/api depends on src/, never the
reverse). "Supervisor" latency is split into its real phases (Cosmos context load, the one
semantic call, Cosmos turn persistence); "ReAct"/"RAG" latency is not further broken down here —
both happen inside whichever Agent.handle() runs, and this class deliberately has zero knowledge
of Agent internals (see class docstring above) so it cannot time them individually without
violating that boundary. See docs/sprint_04/decisions.md for the measured breakdown and why a
deeper per-Agent breakdown was judged out of scope.
"""

from __future__ import annotations

import logging
import time
from uuid import uuid4

from src.agents.shared.semantic_models import AlternativeIntent
from src.core.tool_calling.models import ReActEventSink
from src.domain.conversation import Conversation, Message, MessageRole
from src.domain.conversation_repository import ConversationRepository
from src.llm.provider import LLMProvider
from src.prompts.manager import PromptManager
from src.supervisor.context import load_conversation_context
from src.supervisor.intent import IntentResolver
from src.supervisor.models import (
    AgentRequest,
    AgentResponse,
    ConversationContext,
    IntentCategory,
    SupervisorConfig,
)
from src.supervisor.registry import Agent, AgentRegistry
from src.supervisor.semantic_routing import RoutingDecision, SemanticRoutingConfig, resolve_turn

_logger = logging.getLogger(__name__)


class SupervisorOrchestrator:
    """Registry-driven Supervisor.

    Pipeline: load ConversationContext -> ONE semantic turn interpretation
    (src.supervisor.semantic_routing.resolve_turn) -> resolve Agent from the registry -> invoke
    Agent (reusing the same interpretation, never re-requesting it) -> persist the turn -> return
    AgentResponse. Agent selection is a single dict lookup inside AgentRegistry, with one
    uniform, agent-agnostic fallback: a follow-up message that resolves to UNKNOWN (whether
    semantically or via the deterministic fallback) and is NOT a genuine clarification case
    stays with whichever Agent is already handling this conversation, rather than being
    misrouted to FallbackAgent — this is not per-agent-type branching, it applies identically
    regardless of which Agent that is.
    """

    def __init__(
        self,
        conversation_repository: ConversationRepository,
        intent_resolver: IntentResolver,
        agent_registry: AgentRegistry,
        prompt_manager: PromptManager,
        llm_provider: LLMProvider,
        config: SupervisorConfig | None = None,
    ) -> None:
        self._conversation_repository = conversation_repository
        self._intent_resolver = intent_resolver
        self._agent_registry = agent_registry
        self._prompt_manager = prompt_manager
        self._llm_provider = llm_provider
        self._config = config or SupervisorConfig()
        self._semantic_routing_config = SemanticRoutingConfig(
            high_confidence=self._config.semantic_routing_high_confidence,
            low_confidence=self._config.semantic_routing_low_confidence,
        )

    async def handle(
        self, request: AgentRequest, on_react_event: ReActEventSink | None = None
    ) -> AgentResponse:
        pipeline_start = time.perf_counter()

        context_start = time.perf_counter()
        context = await load_conversation_context(
            repository=self._conversation_repository,
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            max_history_messages=self._config.max_history_messages,
        )
        context_load_ms = (time.perf_counter() - context_start) * 1000

        semantic_start = time.perf_counter()
        decision = await resolve_turn(
            message=request.message,
            context=context,
            prompt_manager=self._prompt_manager,
            llm_provider=self._llm_provider,
            correlation_id=request.correlation_id,
            user_id=request.user_id,
            config=self._semantic_routing_config,
            rule_based_resolver=self._intent_resolver,
        )
        semantic_ms = (time.perf_counter() - semantic_start) * 1000
        agent = self._resolve_agent(decision, context)

        agent_start = time.perf_counter()
        response = await agent.handle(
            request=request,
            context=context,
            on_react_event=on_react_event,
            turn_interpretation=decision.turn_interpretation,
            turn_interpretation_diagnostic=decision.diagnostic,
        )
        agent_handle_ms = (time.perf_counter() - agent_start) * 1000
        # PBI-14-04 section 20: real (never fabricated) routing telemetry for observability — see
        # AgentResponse.routing_diagnostics's own docstring for why this is a dedicated field,
        # never `metadata` (which persists into the Conversation document).
        response = response.model_copy(
            update={"routing_diagnostics": _routing_diagnostics_payload(decision)}
        )

        persist_start = time.perf_counter()
        await self._persist_turn(context=context, request=request, response=response)
        persist_ms = (time.perf_counter() - persist_start) * 1000

        _logger.info(
            "supervisor_turn_latency",
            extra={
                "correlationId": request.correlation_id,
                "conversationId": context.conversation_id,
                "agent": response.agent,
                "routingSource": decision.routing_source,
                "contextLoadMs": round(context_load_ms, 1),
                "semanticMs": round(semantic_ms, 1),
                "agentHandleMs": round(agent_handle_ms, 1),
                "persistMs": round(persist_ms, 1),
                "totalMs": round((time.perf_counter() - pipeline_start) * 1000, 1),
            },
        )

        return response

    def _resolve_agent(self, decision: RoutingDecision, context: ConversationContext) -> Agent:
        # A genuine clarification case always interrupts (FallbackAgent asks the clarifying
        # question) — it must never silently continue with whatever agent handled a prior,
        # possibly unrelated turn. Only the plain "no idea what this is" UNKNOWN case falls back
        # to conversation continuity, exactly like the pre-PBI-14-04 behavior.
        if decision.requires_clarification:
            return self._agent_registry.resolve(IntentCategory.UNKNOWN)
        if decision.category != IntentCategory.UNKNOWN or context.current_agent is None:
            return self._agent_registry.resolve(decision.category)
        for agent in self._agent_registry.list():
            if agent.name == context.current_agent:
                return agent
        return self._agent_registry.resolve(decision.category)

    async def _persist_turn(
        self,
        context: ConversationContext,
        request: AgentRequest,
        response: AgentResponse,
    ) -> None:
        user_message = Message(
            role=MessageRole.USER,
            content=request.message,
            correlation_id=request.correlation_id,
        )
        # PBI-13-01: the ASSISTANT message's id is the caller's pre-generated one when present
        # (see AgentRequest.message_id) — this is the id a RunRecord correlates with
        # ("associated run_id for assistant responses"). Falls back to a freshly generated id
        # otherwise, exactly equivalent to Message.id's own default_factory, so behavior is
        # unchanged for every caller that does not set message_id.
        agent_message = Message(
            id=request.message_id or str(uuid4()),
            role=MessageRole.ASSISTANT,
            content=response.response,
            correlation_id=request.correlation_id,
        )

        if context.is_new:
            conversation = Conversation(
                id=context.conversation_id,
                user_id=context.user_id,
                messages=[user_message, agent_message],
                current_agent=response.agent,
                correlation_id=request.correlation_id,
                metadata=response.metadata,
            )
            await self._conversation_repository.create_conversation(conversation)
            return

        await self._conversation_repository.append_message(
            context.user_id, context.conversation_id, user_message
        )
        await self._conversation_repository.append_message(
            context.user_id,
            context.conversation_id,
            agent_message,
            metadata=response.metadata,
            current_agent=response.agent,
        )


def _routing_diagnostics_payload(decision: RoutingDecision) -> dict[str, str]:
    """Real (never fabricated) routing telemetry for observability (PBI-14-04 section 20) —
    built directly from the RoutingDecision src.supervisor.semantic_routing.resolve_turn already
    computed, so this can never drift from the actual routing decision it describes.
    alternativeIntents/requiresClarification are new in PBI-14-04; routingConfidence/
    routingSource/routingReason existed since PBI-14-03 and keep their exact prior meaning where
    routing_source is still "deterministic_keyword"-shaped (now "deterministic_fallback")."""
    alternative_intents: list[AlternativeIntent] = decision.turn_interpretation.alternative_intents
    return {
        "routingConfidence": str(decision.turn_interpretation.intent_confidence),
        "routingSource": decision.routing_source,
        "routingReason": decision.routing_reason,
        "requiresClarification": str(decision.requires_clarification),
        "alternativeIntents": ",".join(a.intent for a in alternative_intents),
    }

"""Concrete orchestration engine implementing the Supervisor Protocol.

Depends only on interfaces (ConversationRepository, IntentResolver, AgentRegistry) plus a
typed SupervisorConfig — all injected through the constructor, no globals. This class never
imports or references any concrete Agent implementation; adding a new agent never requires
changing this file.

PBI-04-04 (performance requirement): each pipeline phase is timed and logged (never raised,
never blocking) via the standard library `logging` module — deliberately not
apps.api.src.observability (this is a reusable src/ module; apps/api depends on src/, never the
reverse). "Supervisor" latency is split into its two real phases (Cosmos context load, Cosmos
turn persistence); "LLM"/"Tool Calling"/"RAG" latency is not further broken down here — all
three happen inside whichever Agent.handle() runs, and this class deliberately has zero
knowledge of Agent internals (see class docstring above) so it cannot time them individually
without violating that boundary. See docs/sprint_04/decisions.md for the measured breakdown
and why a deeper per-Agent breakdown was judged out of this PBI's scope.
"""

from __future__ import annotations

import logging
import time
from uuid import uuid4

from src.core.tool_calling.models import ReActEventSink
from src.domain.conversation import Conversation, Message, MessageRole
from src.domain.conversation_repository import ConversationRepository
from src.supervisor.context import load_conversation_context
from src.supervisor.intent import IntentResolver
from src.supervisor.models import (
    AgentRequest,
    AgentResponse,
    ConversationContext,
    Intent,
    IntentCategory,
    SupervisorConfig,
)
from src.supervisor.registry import Agent, AgentRegistry

_logger = logging.getLogger(__name__)


class SupervisorOrchestrator:
    """Registry-driven Supervisor.

    Pipeline: load ConversationContext -> resolve Intent -> resolve Agent from the registry
    -> invoke Agent -> persist the turn -> return AgentResponse. Agent selection is a single
    dict lookup inside AgentRegistry, with one uniform, agent-agnostic fallback: a follow-up
    message that the keyword-based IntentResolver cannot classify (e.g. a bare policy number
    or a plain "yes"/"no" answer mid claims-intake) stays with whichever Agent is already
    handling this conversation, rather than being misrouted to FallbackAgent — this is not
    per-agent-type branching, it applies identically regardless of which Agent that is.
    """

    def __init__(
        self,
        conversation_repository: ConversationRepository,
        intent_resolver: IntentResolver,
        agent_registry: AgentRegistry,
        config: SupervisorConfig | None = None,
    ) -> None:
        self._conversation_repository = conversation_repository
        self._intent_resolver = intent_resolver
        self._agent_registry = agent_registry
        self._config = config or SupervisorConfig()

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

        intent = await self._intent_resolver.resolve(request.message)
        agent = self._resolve_agent(intent, context)

        agent_start = time.perf_counter()
        response = await agent.handle(request=request, context=context, on_react_event=on_react_event)
        agent_handle_ms = (time.perf_counter() - agent_start) * 1000

        persist_start = time.perf_counter()
        await self._persist_turn(context=context, request=request, response=response)
        persist_ms = (time.perf_counter() - persist_start) * 1000

        _logger.info(
            "supervisor_turn_latency",
            extra={
                "correlationId": request.correlation_id,
                "conversationId": context.conversation_id,
                "agent": response.agent,
                "contextLoadMs": round(context_load_ms, 1),
                "agentHandleMs": round(agent_handle_ms, 1),
                "persistMs": round(persist_ms, 1),
                "totalMs": round((time.perf_counter() - pipeline_start) * 1000, 1),
            },
        )

        return response

    def _resolve_agent(self, intent: Intent, context: ConversationContext) -> Agent:
        if intent.category != IntentCategory.UNKNOWN or context.current_agent is None:
            return self._agent_registry.resolve(intent.category)
        for agent in self._agent_registry.list():
            if agent.name == context.current_agent:
                return agent
        return self._agent_registry.resolve(intent.category)

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

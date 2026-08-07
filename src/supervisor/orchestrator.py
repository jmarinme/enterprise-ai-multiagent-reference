"""Concrete orchestration engine implementing the Supervisor Protocol.

Depends only on interfaces (ConversationRepository, IntentResolver, AgentRegistry) plus a
typed SupervisorConfig — all injected through the constructor, no globals. This class never
imports or references any concrete Agent implementation; adding a new agent never requires
changing this file.
"""

from __future__ import annotations

from src.domain.conversation import Conversation, Message, MessageRole
from src.domain.conversation_repository import ConversationRepository
from src.supervisor.context import load_conversation_context
from src.supervisor.intent import IntentResolver
from src.supervisor.models import (
    AgentRequest,
    AgentResponse,
    ConversationContext,
    SupervisorConfig,
)
from src.supervisor.registry import AgentRegistry


class SupervisorOrchestrator:
    """Registry-driven Supervisor.

    Pipeline: load ConversationContext -> resolve Intent -> resolve Agent from the registry
    -> invoke Agent -> persist the turn -> return AgentResponse. No if/else or switch
    statements select the agent — resolution is a single dict lookup inside AgentRegistry.
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

    async def handle(self, request: AgentRequest) -> AgentResponse:
        context = await load_conversation_context(
            repository=self._conversation_repository,
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            max_history_messages=self._config.max_history_messages,
        )

        intent = await self._intent_resolver.resolve(request.message)
        agent = self._agent_registry.resolve(intent.category)
        response = await agent.handle(request=request, context=context)

        await self._persist_turn(context=context, request=request, response=response)

        return response

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
        agent_message = Message(
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
            )
            await self._conversation_repository.create_conversation(conversation)
            return

        await self._conversation_repository.append_message(
            context.user_id, context.conversation_id, user_message
        )
        await self._conversation_repository.append_message(
            context.user_id, context.conversation_id, agent_message
        )

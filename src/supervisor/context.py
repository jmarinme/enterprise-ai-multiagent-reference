"""Loads or initializes the ConversationContext the Supervisor operates on.

Depends only on the ConversationRepository Protocol (PBI-00-05) — no concrete adapter,
no Azure dependency.
"""

from __future__ import annotations

from uuid import uuid4

from src.domain.conversation_repository import ConversationRepository
from src.supervisor.models import ConversationContext


async def load_conversation_context(
    repository: ConversationRepository,
    user_id: str,
    conversation_id: str | None,
    max_history_messages: int = 20,
) -> ConversationContext:
    """Load an existing conversation's context, or construct a fresh one if absent.

    max_history_messages bounds how much prior history is loaded into context, so a long
    conversation does not grow the in-context history unboundedly.
    """
    if conversation_id:
        conversation = await repository.get_conversation(user_id, conversation_id)
        if conversation is not None:
            history = conversation.messages
            if max_history_messages > 0:
                history = history[-max_history_messages:]
            return ConversationContext(
                conversation_id=conversation.id,
                user_id=conversation.user_id,
                messages=list(history),
                summary=conversation.summary,
                is_new=False,
            )

    return ConversationContext(
        conversation_id=conversation_id or str(uuid4()),
        user_id=user_id,
        messages=[],
        summary=None,
        is_new=True,
    )

"""In-memory ConversationRepository for local development and unit tests. Requires no
Azure or Cosmos DB connectivity — the default provider for Sprint 0 local execution.
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.domain.conversation import Conversation, Message


class InMemoryConversationRepository:
    """ConversationRepository backed by an in-process dict.

    Returns are deep copies so external mutation cannot corrupt stored state, mirroring
    the semantics of a real out-of-process database. Not intended for production use.
    """

    def __init__(self) -> None:
        self._conversations: dict[tuple[str, str], Conversation] = {}

    async def create_conversation(self, conversation: Conversation) -> Conversation:
        key = (conversation.user_id, conversation.id)
        stored = conversation.model_copy(deep=True)
        self._conversations[key] = stored
        return stored.model_copy(deep=True)

    async def get_conversation(self, user_id: str, conversation_id: str) -> Conversation | None:
        stored = self._conversations.get((user_id, conversation_id))
        return stored.model_copy(deep=True) if stored else None

    async def list_conversations(self, user_id: str) -> list[Conversation]:
        matches = [c for (uid, _cid), c in self._conversations.items() if uid == user_id]
        matches.sort(key=lambda c: c.created_at, reverse=True)
        return [c.model_copy(deep=True) for c in matches]

    async def append_message(
        self,
        user_id: str,
        conversation_id: str,
        message: Message,
        metadata: dict[str, str] | None = None,
    ) -> Conversation:
        key = (user_id, conversation_id)
        stored = self._conversations.get(key)
        if stored is None:
            raise ValueError(f"Conversation {conversation_id} not found for user {user_id}")
        stored.messages.append(message)
        if metadata is not None:
            stored.metadata = metadata
        stored.updated_at = datetime.now(UTC)
        return stored.model_copy(deep=True)

"""Abstract contract for conversation persistence. Concrete adapters live under
src/services/conversation_store/ (in-memory for local dev/tests, Cosmos DB for Azure).
"""

from __future__ import annotations

from typing import Protocol

from src.domain.conversation import Conversation, Message


class ConversationRepository(Protocol):
    """Persistence contract for conversation history, partitioned by user_id."""

    async def create_conversation(self, conversation: Conversation) -> Conversation:
        """Persist a new conversation and return the stored representation."""
        ...

    async def get_conversation(self, user_id: str, conversation_id: str) -> Conversation | None:
        """Point-read a single conversation by its partition key and id."""
        ...

    async def list_conversations(self, user_id: str) -> list[Conversation]:
        """List all conversations for one synthetic user, newest first."""
        ...

    async def append_message(
        self,
        user_id: str,
        conversation_id: str,
        message: Message,
        metadata: dict[str, str] | None = None,
    ) -> Conversation:
        """Append a message to an existing conversation and return the updated conversation.

        When metadata is provided, it replaces the conversation's stored metadata (the
        Agent's latest working-state snapshot) — never merged, since the Agent always sends
        its complete current state, not a partial patch.
        """
        ...

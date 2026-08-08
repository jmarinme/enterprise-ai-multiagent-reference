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
        current_agent: str | None = None,
    ) -> Conversation:
        """Append a message to an existing conversation and return the updated conversation.

        When metadata is provided, it replaces the conversation's stored metadata (the
        Agent's latest working-state snapshot) — never merged, since the Agent always sends
        its complete current state, not a partial patch.

        When current_agent is provided (PBI-05-01), it replaces the conversation's stored
        current_agent — without this, a conversation's current_agent would be frozen at
        whichever Agent handled its very first turn forever, since it was previously only ever
        set at creation time. src.supervisor.orchestrator.SupervisorOrchestrator's own
        "stay with the current agent on an ambiguous follow-up" fallback (PBI-01-05) reads this
        field, so a stale value would misroute a follow-up back to the *original* agent even
        after a legitimate cross-domain handoff (e.g. Claims -> Broker) — exactly the failure
        mode PBI-05-01 requirement 5 explicitly calls out.
        """
        ...

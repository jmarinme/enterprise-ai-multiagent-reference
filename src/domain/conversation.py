"""Domain models for the conversation history store (CLAUDE.md §4.3).

These models are the Cosmos DB document contract for the `conversations` container: one
document per conversation, partitioned by `userId`, with an embedded, ordered list of
messages. Field names are camelCase on the wire (matching the documented Cosmos schema)
while Python code uses snake_case attributes, via a shared camelCase alias generator.

Core business truth (policies, claims, payments, commissions) must never be modeled or
stored here — only conversational state.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ConversationStatus(str, Enum):
    ACTIVE = "active"
    ESCALATED = "escalated"
    CLOSED = "closed"


class Message(_CamelModel):
    """A single turn within a conversation."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    role: MessageRole
    content: str
    created_at: datetime = Field(default_factory=_utcnow)
    correlation_id: str | None = None


class Conversation(_CamelModel):
    """A synthetic user's conversation, partitioned by user_id (Cosmos partition key /userId)."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    conversation_id: str = Field(default="")
    user_id: str
    status: ConversationStatus = ConversationStatus.ACTIVE
    current_agent: str | None = None
    summary: str | None = None
    messages: list[Message] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    feedback: dict[str, str] | None = None
    correlation_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    def model_post_init(self, context: Any, /) -> None:
        if not self.conversation_id:
            self.conversation_id = self.id

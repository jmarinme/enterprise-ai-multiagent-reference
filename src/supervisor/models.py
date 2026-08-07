"""Typed models for the Supervisor orchestration pipeline.

These are internal orchestration models, distinct from the transport-layer request/response
models apps/api defines for POST /chat (apps/api/src/api/routes/chat.py).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from src.domain.conversation import Message


class IntentCategory(str, Enum):
    """Synthetic intent categories. Rule-based only — see src/supervisor/intent.py."""

    CLAIMS = "CLAIMS"
    BROKER = "BROKER"
    COMMERCIAL = "COMMERCIAL"
    UNKNOWN = "UNKNOWN"


class Intent(BaseModel):
    """Result of intent resolution."""

    category: IntentCategory
    confidence: float = 1.0


class AgentRequest(BaseModel):
    """A single inbound chat turn, passed to the Supervisor and then to the selected Agent."""

    message: str
    user_id: str
    conversation_id: str | None = None
    correlation_id: str | None = None


class ConversationContext(BaseModel):
    """Conversation state loaded (or freshly initialized) before an Agent is invoked."""

    conversation_id: str
    user_id: str
    messages: list[Message] = Field(default_factory=list)
    summary: str | None = None
    is_new: bool = False
    metadata: dict[str, str] = Field(default_factory=dict)
    current_agent: str | None = None


class AgentResponse(BaseModel):
    """An Agent's reply, returned by the Supervisor to the caller."""

    conversation_id: str
    agent: str
    intent: IntentCategory
    response: str
    metadata: dict[str, str] = Field(default_factory=dict)


class SupervisorConfig(BaseModel):
    """Runtime configuration injected into the Supervisor (never read from globals)."""

    max_history_messages: int = 20

"""Typed models for the Supervisor orchestration pipeline.

These are internal orchestration models, distinct from the transport-layer request/response
models apps/api defines for POST /chat (apps/api/src/api/routes/chat.py).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from src.core.tool_calling.models import ToolCallResult
from src.domain.conversation import Message
from src.rag.grounding_models import Citation, GroundingMetadata


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
    """An Agent's reply, returned by the Supervisor to the caller.

    citations/grounding_metadata (PBI-02-03) and tool_calls (PBI-02-04) are typed pass-throughs,
    exactly like metadata already was: SupervisorOrchestrator never constructs, inspects, or
    reasons about them — it only ever returns whatever AgentResponse the selected Agent
    produced. Importing these *types* here is a data-contract dependency, not a behavioral
    one — the Supervisor still contains zero knowledge-retrieval or tool-calling code and
    never imports KnowledgeProvider/KnowledgeRetriever/ToolCallingOrchestrator/any concrete
    implementation, which is what "Supervisor remains unaware of the Knowledge implementation"
    (PBI-02-01) actually protects, extended identically to Tool Calling."""

    conversation_id: str
    agent: str
    intent: IntentCategory
    response: str
    metadata: dict[str, str] = Field(default_factory=dict)
    citations: list[Citation] = Field(default_factory=list)
    grounding_metadata: GroundingMetadata | None = None
    tool_calls: list[ToolCallResult] = Field(default_factory=list)


class SupervisorConfig(BaseModel):
    """Runtime configuration injected into the Supervisor (never read from globals)."""

    max_history_messages: int = 20

"""Typed models for the Supervisor orchestration pipeline.

These are internal orchestration models, distinct from the transport-layer request/response
models apps/api defines for POST /chat (apps/api/src/api/routes/chat.py).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from src.core.tool_calling.models import LLMUsageTotal, ToolCallResult
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
    # PBI-13-01: when the caller (apps/api/src/api/routes/chat.py) pre-generates a message id,
    # SupervisorOrchestrator._persist_turn uses it for the persisted user/assistant Message
    # pair instead of letting Message.id auto-generate — so the caller can correlate a run with
    # the exact message it produced without re-reading the conversation. None (default)
    # preserves every existing caller's exact prior behavior (auto-generated ids).
    message_id: str | None = None


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
    # PBI-13-01: business/agentic observability additions, both purely additive (default None/
    # empty preserves every existing caller's exact prior behavior). Populated only by an Agent
    # that actually ran the Tool Calling loop (see ToolCallingResponse.model/usage) — None for
    # FallbackAgent, which never calls an LLM.
    model: str | None = None
    token_usage: LLMUsageTotal | None = None
    # PBI-14-03 section 20: real routing telemetry, set only by SupervisorOrchestrator (never by
    # an Agent) after Agent.handle() returns. Deliberately a separate field from `metadata`
    # above: `metadata` round-trips into the persisted Conversation document (see
    # SupervisorOrchestrator._persist_turn) — chat history is not the right place for
    # observability-only routing diagnostics, so this field is read by the observability call
    # site (apps/api/src/api/routes/chat.py) and never persisted to the conversation store.
    routing_diagnostics: dict[str, str] | None = None


class SupervisorConfig(BaseModel):
    """Runtime configuration injected into the Supervisor (never read from globals)."""

    max_history_messages: int = 20
    # PBI-14-04 section 8: semantic-first routing confidence thresholds. Operational STARTING
    # values, not a statistical guarantee — see src.supervisor.semantic_routing.
    # SemanticRoutingConfig's own docstring for the full rationale.
    semantic_routing_high_confidence: float = 0.7
    semantic_routing_low_confidence: float = 0.4

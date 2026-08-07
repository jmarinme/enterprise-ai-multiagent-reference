"""POST /chat — the platform's single conversational entry point.

This route contains no business logic: it translates the HTTP request into an
src.supervisor.models.AgentRequest, delegates entirely to the Supervisor, and translates the
result back into an HTTP response.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from src.core.tool_calling.models import ToolCallResult
from src.rag.grounding_models import Citation, GroundingMetadata
from src.supervisor.models import AgentRequest
from src.supervisor.orchestrator import SupervisorOrchestrator

from api.dependencies import get_supervisor

router = APIRouter(tags=["chat"])


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ChatRequest(_CamelModel):
    message: str
    conversation_id: str | None = None
    user_id: str


class ChatResponse(_CamelModel):
    conversation_id: str
    agent: str
    intent: str
    response: str
    # Deliberately generic (not claims-specific typed fields): keeps this route free of any
    # business logic, per this file's own docstring. An Agent may use it to expose working
    # state (e.g. ClaimsAgent's claimsIntakeState) to a future richer client; existing clients
    # that ignore unknown fields are unaffected.
    metadata: dict[str, str] = Field(default_factory=dict)
    # New, optional (PBI-02-03): typed citations for a grounded response, empty for any Agent
    # that does not use the Grounding layer. Additive — existing clients unaffected.
    citations: list[Citation] = Field(default_factory=list)
    grounding_metadata: GroundingMetadata | None = None
    # New, optional (PBI-02-04): typed outcomes of any LLM-requested Tool calls, empty for any
    # Agent that does not use controlled Tool Calling. Additive — existing clients unaffected.
    tool_calls: list[ToolCallResult] = Field(default_factory=list)


@router.post("/chat", response_model=ChatResponse)
async def post_chat(
    chat_request: ChatRequest,
    supervisor: SupervisorOrchestrator = Depends(get_supervisor),
) -> ChatResponse:
    """Route a chat message through the Supervisor and return the selected agent's response."""
    agent_request = AgentRequest(
        message=chat_request.message,
        user_id=chat_request.user_id,
        conversation_id=chat_request.conversation_id,
    )

    agent_response = await supervisor.handle(agent_request)

    return ChatResponse(
        conversation_id=agent_response.conversation_id,
        agent=agent_response.agent,
        intent=agent_response.intent.value,
        response=agent_response.response,
        metadata=agent_response.metadata,
        citations=agent_response.citations,
        grounding_metadata=agent_response.grounding_metadata,
        tool_calls=agent_response.tool_calls,
    )

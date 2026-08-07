"""POST /chat — the platform's single conversational entry point.

This route contains no business logic: it translates the HTTP request into an
src.supervisor.models.AgentRequest, delegates entirely to the Supervisor, and translates the
result back into an HTTP response.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
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
    )

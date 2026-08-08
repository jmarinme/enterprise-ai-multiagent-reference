"""GET /conversations, GET /conversations/{conversationId} — conversation-history endpoints
(PBI-04-04), backing the Web UI's ChatGPT-style history sidebar.

Reuses src.domain.conversation_repository.ConversationRepository's already-implemented
list_conversations/get_conversation methods exactly as-is (both the in-memory and Cosmos DB
adapters already had these — only the HTTP surface was missing). Like chat.py, this route
contains no business logic: it translates repository reads into the HTTP response shape.

No text-search parameter is added at the repository/query level: list_conversations already
returns every conversation for one userId (a single, already-partition-scoped Cosmos query,
newest first) and this platform's synthetic conversation volume per user is small — the Web UI
filters client-side. Adding a server-side CONTAINS() query is deferred to a real PBI if
conversation volume ever justifies it (see docs/sprint_04/decisions.md).
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from src.domain.conversation import Message
from src.domain.conversation_repository import ConversationRepository

from api.dependencies import get_conversation_repository_dep

router = APIRouter(tags=["conversations"])

_TITLE_MAX_LENGTH = 48


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class MessageResponse(_CamelModel):
    role: str
    content: str
    created_at: datetime


class ConversationSummaryResponse(_CamelModel):
    conversation_id: str
    title: str
    status: str
    current_agent: str | None = None
    created_at: datetime
    updated_at: datetime


class ConversationDetailResponse(_CamelModel):
    conversation_id: str
    title: str
    status: str
    current_agent: str | None = None
    messages: list[MessageResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


def _derive_title(messages: list[Message]) -> str:
    """A short, automatic title from the conversation's first user message — naturally in
    whichever language the caller used, satisfying the "automatic Spanish titles" requirement
    without a separate translation step, since Spanish is this platform's default language."""
    for message in messages:
        if message.role.value == "user":
            text = message.content.strip()
            if len(text) <= _TITLE_MAX_LENGTH:
                return text
            return text[:_TITLE_MAX_LENGTH].rstrip() + "…"
    return "Nueva conversación"


@router.get("/conversations", response_model=list[ConversationSummaryResponse])
async def list_conversations(
    user_id: str = Query(alias="userId"),
    repository: ConversationRepository = Depends(get_conversation_repository_dep),
) -> list[ConversationSummaryResponse]:
    """List every conversation for one synthetic user, newest first."""
    conversations = await repository.list_conversations(user_id)
    return [
        ConversationSummaryResponse(
            conversation_id=conversation.conversation_id,
            title=_derive_title(conversation.messages),
            status=conversation.status.value,
            current_agent=conversation.current_agent,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )
        for conversation in conversations
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: str,
    user_id: str = Query(alias="userId"),
    repository: ConversationRepository = Depends(get_conversation_repository_dep),
) -> ConversationDetailResponse:
    """Fetch one full conversation (with messages) for the history sidebar's restore action."""
    conversation = await repository.get_conversation(user_id, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationDetailResponse(
        conversation_id=conversation.conversation_id,
        title=_derive_title(conversation.messages),
        status=conversation.status.value,
        current_agent=conversation.current_agent,
        messages=[
            MessageResponse(role=message.role.value, content=message.content, created_at=message.created_at)
            for message in conversation.messages
        ],
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )

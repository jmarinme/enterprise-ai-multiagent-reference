"""GET /observability/summary, /observability/conversations, /observability/conversations/{id},
/observability/runs/{id} — the business/agentic observability read API (PBI-13-01 §19).

No `/api` prefix, matching this backend's existing flat-root convention (chat.py,
conversations.py — see apps/api/src/main.py, no router here or elsewhere passes `prefix=`).

Every route requires api.observability_access.require_observability_access — centralized,
config-driven authorization (PBI-13-01 §16), never per-route ad hoc checks. Server-side
pagination and filters only; no route here ever retrieves every conversation/run in one
request (PBI-13-01 §10/§19).
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from src.domain.conversation_repository import ConversationRepository
from src.domain.observability import ConversationSummary, RunRecord
from src.domain.observability_repository import ObservabilityFilters
from src.observability.masking import mask_pii
from src.observability.service import ObservabilityService

from api.auth.models import AuthenticatedUser
from api.dependencies import get_conversation_repository_dep, get_observability_service
from api.observability_access import require_observability_access
from src.config.settings import ObservabilitySettings

router = APIRouter(tags=["observability"])

_DEFAULT_PAGE_SIZE = 25
_MAX_PAGE_SIZE = 100


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class SummaryKpisResponse(_CamelModel):
    conversation_count: int | None = None
    run_count: int | None = None
    success_rate: float | None = None
    average_latency_ms: float | None = None
    total_input_tokens: int | None = None
    total_output_tokens: int | None = None
    total_estimated_cost_usd: float | None = None


class ConversationSummaryResponse(_CamelModel):
    conversation_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    status: str | None = None
    primary_domain: str | None = None
    message_count: int | None = None
    run_count: int
    total_input_tokens: int
    total_output_tokens: int
    total_estimated_cost_usd: float
    operational_quality_score: float | None = None
    business_outcome: str | None = None
    last_message_preview: str | None = None


class ConversationListResponse(_CamelModel):
    items: list[ConversationSummaryResponse]
    total: int
    skip: int
    limit: int


class RunToolCallResponse(_CamelModel):
    call_id: str
    tool_name: str
    success: bool
    error_type: str | None = None
    latency_ms: float | None = None


class RunResponse(_CamelModel):
    run_id: str
    conversation_id: str
    message_id: str | None = None
    trace_id: str | None = None
    user_id: str
    created_at: datetime
    detected_intent: str | None = None
    intent_confidence: float | None = None
    selected_agent: str | None = None
    routing_reason: str | None = None
    tool_calls: list[RunToolCallResponse] = Field(default_factory=list)
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    pricing_snapshot_version: str | None = None
    total_latency_ms: float | None = None
    iterations: int | None = None
    stopped_due_to_max_iterations: bool | None = None
    stopped_due_to_timeout: bool | None = None
    final_status: str | None = None
    error_category: str | None = None


class ConversationMessageResponse(_CamelModel):
    id: str
    role: str
    content: str
    created_at: datetime
    run_id: str | None = None


class ConversationDetailResponse(_CamelModel):
    summary: ConversationSummaryResponse
    messages: list[ConversationMessageResponse] = Field(default_factory=list)
    runs: list[RunResponse] = Field(default_factory=list)


def _to_run_response(run: RunRecord) -> RunResponse:
    return RunResponse(
        run_id=run.run_id,
        conversation_id=run.conversation_id,
        message_id=run.message_id,
        trace_id=run.trace_id,
        user_id=run.user_id,
        created_at=run.created_at,
        detected_intent=run.detected_intent,
        intent_confidence=run.intent_confidence,
        selected_agent=run.selected_agent,
        routing_reason=run.routing_reason,
        tool_calls=[
            RunToolCallResponse(
                call_id=call.call_id,
                tool_name=call.tool_name,
                success=call.success,
                error_type=call.error_type,
                latency_ms=call.latency_ms,
            )
            for call in run.tool_calls
        ],
        model=run.model,
        input_tokens=run.token_usage.prompt_tokens if run.token_usage else None,
        output_tokens=run.token_usage.completion_tokens if run.token_usage else None,
        estimated_cost_usd=run.estimated_cost_usd,
        pricing_snapshot_version=run.pricing_snapshot_version,
        total_latency_ms=run.total_latency_ms,
        iterations=run.iterations,
        stopped_due_to_max_iterations=run.stopped_due_to_max_iterations,
        stopped_due_to_timeout=run.stopped_due_to_timeout,
        final_status=run.final_status,
        error_category=run.error_category,
    )


def _to_summary_response(
    summary: ConversationSummary, *, pii_masking: bool
) -> ConversationSummaryResponse:
    return ConversationSummaryResponse(
        conversation_id=summary.conversation_id,
        user_id=summary.user_id,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
        status=summary.status,
        primary_domain=summary.primary_domain,
        message_count=summary.message_count,
        run_count=summary.run_count,
        total_input_tokens=summary.total_input_tokens,
        total_output_tokens=summary.total_output_tokens,
        total_estimated_cost_usd=summary.total_estimated_cost_usd,
        operational_quality_score=summary.operational_quality_score,
        business_outcome=summary.business_outcome,
        last_message_preview=(
            mask_pii(summary.last_message_preview) if pii_masking else summary.last_message_preview
        ),
    )


@router.get("/observability/summary", response_model=SummaryKpisResponse)
async def get_summary(
    _current_user: AuthenticatedUser = Depends(require_observability_access),
    user_id: str | None = Query(default=None, alias="userId"),
    agent: str | None = Query(default=None),
    status: str | None = Query(default=None),
    date_from: str | None = Query(default=None, alias="dateFrom"),
    date_to: str | None = Query(default=None, alias="dateTo"),
    search: str | None = Query(default=None),
    observability: ObservabilityService = Depends(get_observability_service),
) -> SummaryKpisResponse:
    filters = ObservabilityFilters(
        user_id=user_id, agent=agent, status=status, date_from=date_from, date_to=date_to, search=search
    )
    kpis = await observability.get_summary_kpis(filters)
    return SummaryKpisResponse(**kpis.model_dump())


@router.get("/observability/conversations", response_model=ConversationListResponse)
async def list_observability_conversations(
    _current_user: AuthenticatedUser = Depends(require_observability_access),
    user_id: str | None = Query(default=None, alias="userId"),
    agent: str | None = Query(default=None),
    status: str | None = Query(default=None),
    date_from: str | None = Query(default=None, alias="dateFrom"),
    date_to: str | None = Query(default=None, alias="dateTo"),
    search: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=_DEFAULT_PAGE_SIZE, ge=1, le=_MAX_PAGE_SIZE),
    observability: ObservabilityService = Depends(get_observability_service),
) -> ConversationListResponse:
    """Server-side paginated, filtered conversation list — never retrieves every conversation
    in one request (PBI-13-01 §10)."""
    filters = ObservabilityFilters(
        user_id=user_id, agent=agent, status=status, date_from=date_from, date_to=date_to, search=search
    )
    items, total = await observability.list_conversation_summaries(filters, skip=skip, limit=limit)
    pii_masking = ObservabilitySettings().observability_pii_masking
    return ConversationListResponse(
        items=[_to_summary_response(item, pii_masking=pii_masking) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/observability/conversations/{conversation_id}", response_model=ConversationDetailResponse
)
async def get_observability_conversation(
    conversation_id: str,
    _current_user: AuthenticatedUser = Depends(require_observability_access),
    observability: ObservabilityService = Depends(get_observability_service),
    conversation_repository: ConversationRepository = Depends(get_conversation_repository_dep),
) -> ConversationDetailResponse:
    """Combines the observability summary/run data (own container, own repository) with the
    real message thread (existing ConversationRepository) — the only place this feature reads
    the `conversations` container, and always as a point-read scoped by the summary's own
    user_id, never a client-supplied one."""
    summary = await observability.get_conversation_summary(conversation_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation = await conversation_repository.get_conversation(summary.user_id, conversation_id)
    runs = await observability.list_runs_for_conversation(conversation_id)
    run_by_message_id = {run.message_id: run.run_id for run in runs if run.message_id}
    pii_masking = ObservabilitySettings().observability_pii_masking

    messages = (
        [
            ConversationMessageResponse(
                id=message.id,
                role=message.role.value,
                content=(mask_pii(message.content) or message.content)
                if pii_masking
                else message.content,
                created_at=message.created_at,
                run_id=run_by_message_id.get(message.id),
            )
            for message in conversation.messages
        ]
        if conversation is not None
        else []
    )

    return ConversationDetailResponse(
        summary=_to_summary_response(summary, pii_masking=pii_masking),
        messages=messages,
        runs=[_to_run_response(run) for run in runs],
    )


@router.get("/observability/runs/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    _current_user: AuthenticatedUser = Depends(require_observability_access),
    observability: ObservabilityService = Depends(get_observability_service),
) -> RunResponse:
    run = await observability.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return _to_run_response(run)

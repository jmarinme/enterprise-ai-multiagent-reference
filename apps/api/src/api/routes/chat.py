"""POST /chat — the platform's single conversational entry point.

This route contains no business logic: it translates the HTTP request into an
src.supervisor.models.AgentRequest, delegates entirely to the Supervisor, and translates the
result back into an HTTP response.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from src.core.tool_calling.models import ReActEvent, ToolCallResult
from src.observability.service import ObservabilityService
from src.rag.grounding_models import Citation, GroundingMetadata
from src.supervisor.models import AgentRequest
from src.supervisor.orchestrator import SupervisorOrchestrator

from api.auth.dependency import get_current_user
from api.auth.models import AuthenticatedUser
from api.dependencies import get_observability_service, get_supervisor

router = APIRouter(tags=["chat"])
_logger = logging.getLogger(__name__)


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ChatRequest(_CamelModel):
    message: str
    conversation_id: str | None = None
    # DEPRECATED (PBI-11-01): retained only for backward compatibility with any client still
    # sending it. Never used for authorization — the authenticated caller's identity (derived
    # from the validated Entra ID Bearer token, see api.auth.dependency.get_current_user)
    # always determines which conversation is read or written, regardless of this value. A
    # future PBI may remove this field once no client still sends it.
    user_id: str | None = None


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
    http_request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    supervisor: SupervisorOrchestrator = Depends(get_supervisor),
    observability: ObservabilityService = Depends(get_observability_service),
) -> ChatResponse:
    """Route a chat message through the Supervisor and return the selected agent's response.

    Requires a valid Entra ID Bearer token (PBI-11-01) — current_user.user_id (derived from
    the token's own tid/oid claims) is the only identity ever used, never
    chat_request.user_id (deprecated, ignored for authorization).
    """
    # PBI-13-01: correlation_id was already generated/propagated by CorrelationIdMiddleware
    # (apps/api/src/api/middleware/correlation_id.py) but was never previously threaded into
    # AgentRequest — this is the fix. message_id/run_id are new identifiers this route
    # generates: message_id becomes the persisted assistant Message's own id (see
    # AgentRequest.message_id / SupervisorOrchestrator._persist_turn), run_id identifies this
    # one processing run for observability purposes only (never persisted to the conversation
    # store).
    correlation_id = getattr(http_request.state, "correlation_id", None)
    message_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    started_at = datetime.now(UTC)
    pipeline_start = time.perf_counter()

    react_events: list[ReActEvent] = []

    def _collect_event(event: ReActEvent) -> None:
        react_events.append(event)

    agent_request = AgentRequest(
        message=chat_request.message,
        user_id=current_user.user_id,
        conversation_id=chat_request.conversation_id,
        correlation_id=correlation_id,
        message_id=message_id,
    )

    try:
        agent_response = await supervisor.handle(agent_request, on_react_event=_collect_event)
    except Exception as exc:
        # PBI-13-01 §3: telemetry must never affect the chat response — this records an
        # "error" run for observability purposes only, then re-raises the *original* exception
        # completely unchanged (same type, same traceback), so the HTTP error behavior this
        # route already had is byte-for-byte identical to before this PBI.
        await observability.record_run(
            run_id=run_id,
            conversation_id=chat_request.conversation_id or "",
            message_id=message_id,
            trace_id=correlation_id,
            user_id=current_user.user_id,
            started_at=started_at,
            total_latency_ms=(time.perf_counter() - pipeline_start) * 1000,
            detected_intent=None,
            agent_response=None,
            react_events=react_events,
            error_category=type(exc).__name__,
        )
        raise

    total_latency_ms = (time.perf_counter() - pipeline_start) * 1000
    try:
        # PBI-14-03/PBI-14-04 section 20: real routing telemetry, set by SupervisorOrchestrator
        # itself (never fabricated here) via the dedicated AgentResponse.routing_diagnostics
        # field — observability-only, never persisted to the conversation store.
        routing_diagnostics = agent_response.routing_diagnostics or {}
        raw_confidence = routing_diagnostics.get("routingConfidence")
        intent_confidence = float(raw_confidence) if raw_confidence is not None else None
        raw_alternative_intents = routing_diagnostics.get("alternativeIntents")
        alternative_intents = (
            [i for i in raw_alternative_intents.split(",") if i] if raw_alternative_intents else None
        )
        raw_requires_clarification = routing_diagnostics.get("requiresClarification")
        requires_clarification = (
            raw_requires_clarification == "True" if raw_requires_clarification is not None else None
        )
        await observability.record_run(
            run_id=run_id,
            conversation_id=agent_response.conversation_id,
            message_id=message_id,
            trace_id=correlation_id,
            user_id=current_user.user_id,
            started_at=started_at,
            total_latency_ms=total_latency_ms,
            detected_intent=agent_response.intent.value,
            agent_response=agent_response,
            react_events=react_events,
            intent_confidence=intent_confidence,
            routing_reason=routing_diagnostics.get("routingReason"),
            routing_source=routing_diagnostics.get("routingSource"),
            requires_clarification=requires_clarification,
            alternative_intents=alternative_intents,
        )
    except Exception:
        # already swallows its own failures, but this route must never fail the chat response
        # for any reason connected to observability, including a bug in the call site itself.
        _logger.warning(
            "observability_record_run_call_failed",
            extra={"correlationId": correlation_id, "runId": run_id},
            exc_info=True,
        )

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

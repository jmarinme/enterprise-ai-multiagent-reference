"""ObservabilityService: the single shared abstraction that records business/agentic
observability data (PBI-13-01 §3). Instrumented at one architectural boundary — the API layer,
after SupervisorOrchestrator.handle() returns — rather than scattered across every Agent.

Best-effort and non-blocking by construction: record_run() never raises. A persistence failure
is logged through the existing technical logging mechanism (stdlib `logging`, matching
src.supervisor.orchestrator's own reasoning for using it instead of apps.api.src.observability
directly — this is a reusable src/ module, apps/api depends on src/, never the reverse) and
otherwise swallowed — it must never affect the chat response.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from src.core.tool_calling.models import ReActEvent
from src.domain.observability import (
    ConversationSummary,
    RunRecord,
    RunStatus,
    RunTokenUsage,
    RunToolCall,
    SummaryKpis,
)
from src.domain.observability_repository import ObservabilityFilters, ObservabilityRepository
from src.observability.pricing import PricingCatalog
from src.supervisor.models import AgentResponse

_logger = logging.getLogger(__name__)


class ObservabilityService:
    """Builds a RunRecord from one completed (or failed) processing run and persists it
    best-effort. Also exposes read paths for the observability API routes — a thin pass-through
    to ObservabilityRepository, kept here so routes never depend on the repository directly."""

    def __init__(self, repository: ObservabilityRepository, pricing_catalog: PricingCatalog) -> None:
        self._repository = repository
        self._pricing_catalog = pricing_catalog

    async def record_run(
        self,
        *,
        run_id: str,
        conversation_id: str,
        message_id: str | None,
        trace_id: str | None,
        user_id: str,
        started_at: datetime,
        total_latency_ms: float,
        detected_intent: str | None,
        agent_response: AgentResponse | None,
        react_events: list[ReActEvent],
        error_category: str | None = None,
        intent_confidence: float | None = None,
        routing_reason: str | None = None,
    ) -> None:
        """Never raises. Call from a `try`/`except Exception: logger.warning(...)` at the call
        site is intentionally redundant defense-in-depth with the try/except inside this
        method — both exist because PBI-13-01 §3 requires telemetry failure to never affect the
        chat response under any circumstance.

        intent_confidence/routing_reason (PBI-14-03 section 20): real routing telemetry from
        src.supervisor.orchestrator's own fully-deterministic decision (ADR-0011) — never
        fabricated, None when the caller has nothing real to report (e.g. the error path,
        where routing never completed)."""
        try:
            run = self._build_run_record(
                run_id=run_id,
                conversation_id=conversation_id,
                message_id=message_id,
                trace_id=trace_id,
                user_id=user_id,
                started_at=started_at,
                total_latency_ms=total_latency_ms,
                detected_intent=detected_intent,
                agent_response=agent_response,
                react_events=react_events,
                error_category=error_category,
                intent_confidence=intent_confidence,
                routing_reason=routing_reason,
            )
            await self._repository.record_run(run)
        except Exception:
            _logger.warning(
                "observability_record_run_failed",
                extra={"correlationId": trace_id, "conversationId": conversation_id, "runId": run_id},
                exc_info=True,
            )

    def _build_run_record(
        self,
        *,
        run_id: str,
        conversation_id: str,
        message_id: str | None,
        trace_id: str | None,
        user_id: str,
        started_at: datetime,
        total_latency_ms: float,
        detected_intent: str | None,
        agent_response: AgentResponse | None,
        react_events: list[ReActEvent],
        error_category: str | None,
        intent_confidence: float | None = None,
        routing_reason: str | None = None,
    ) -> RunRecord:
        tool_executed_events = [e for e in react_events if e.event_type == "tool_executed"]
        tool_calls: list[RunToolCall] = []
        if agent_response is not None:
            for index, call in enumerate(agent_response.tool_calls):
                # Best-effort latency correlation: tool_calls and tool_executed events are both
                # appended in identical execution order within ToolCallingOrchestrator.run() —
                # paired by position, never fabricated when the counts don't line up.
                latency_ms = (
                    tool_executed_events[index].latency_ms
                    if index < len(tool_executed_events)
                    else None
                )
                tool_calls.append(
                    RunToolCall(
                        call_id=call.call_id,
                        tool_name=call.tool_name,
                        success=call.success,
                        error_type=call.error_type,
                        latency_ms=latency_ms,
                    )
                )

        model = agent_response.model if agent_response else None
        input_tokens = agent_response.token_usage.prompt_tokens if agent_response and agent_response.token_usage else None
        output_tokens = agent_response.token_usage.completion_tokens if agent_response and agent_response.token_usage else None
        token_usage = None
        if agent_response and agent_response.token_usage:
            token_usage = RunTokenUsage(
                prompt_tokens=agent_response.token_usage.prompt_tokens,
                completion_tokens=agent_response.token_usage.completion_tokens,
                total_tokens=agent_response.token_usage.total_tokens,
            )
        cost, pricing_version = self._pricing_catalog.estimate_cost_usd(
            model, input_tokens, output_tokens
        )

        iterations = None
        stopped_max = None
        stopped_timeout = None
        final_answer_events = [e for e in react_events if e.event_type == "final_answer_reached"]
        if final_answer_events:
            iterations = final_answer_events[-1].iteration
            stopped_max = False
            stopped_timeout = False
        elif any(e.event_type == "stopped_max_iterations" for e in react_events):
            stopped_max = True
            stopped_timeout = False
        elif any(e.event_type == "stopped_timeout" for e in react_events):
            stopped_max = False
            stopped_timeout = True

        # PBI-13-01 Phase 1 deliberately keeps final_status to the two signals reliably
        # observable at this boundary today (a raised exception vs. a produced response).
        # needs_data/escalated/abandoned require the deterministic quality-signal work
        # explicitly scoped to Phase 2 (PBI-13-01 §13/§21) — never fabricated here.
        final_status: RunStatus | None = (
            "error" if error_category else ("completed" if agent_response else None)
        )

        return RunRecord(
            id=run_id,
            run_id=run_id,
            conversation_id=conversation_id,
            message_id=message_id,
            trace_id=trace_id,
            user_id=user_id,
            created_at=started_at,
            detected_intent=detected_intent,
            intent_confidence=intent_confidence,
            selected_agent=agent_response.agent if agent_response else None,
            routing_reason=routing_reason,
            tool_calls=tool_calls,
            model=model,
            token_usage=token_usage,
            estimated_cost_usd=cost,
            pricing_snapshot_version=pricing_version,
            total_latency_ms=total_latency_ms,
            iterations=iterations,
            stopped_due_to_max_iterations=stopped_max,
            stopped_due_to_timeout=stopped_timeout,
            final_status=final_status,
            error_category=error_category,
        )

    async def get_run(self, run_id: str) -> RunRecord | None:
        return await self._repository.get_run(run_id)

    async def list_runs_for_conversation(self, conversation_id: str) -> list[RunRecord]:
        return await self._repository.list_runs_for_conversation(conversation_id)

    async def get_conversation_summary(self, conversation_id: str) -> ConversationSummary | None:
        return await self._repository.get_conversation_summary(conversation_id)

    async def list_conversation_summaries(
        self, filters: ObservabilityFilters, *, skip: int, limit: int
    ) -> tuple[list[ConversationSummary], int]:
        return await self._repository.list_conversation_summaries(filters, skip=skip, limit=limit)

    async def get_summary_kpis(self, filters: ObservabilityFilters) -> SummaryKpis:
        return await self._repository.get_summary_kpis(filters)


def utcnow() -> datetime:
    return datetime.now(UTC)

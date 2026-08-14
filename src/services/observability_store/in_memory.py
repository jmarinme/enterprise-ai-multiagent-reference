"""In-memory ObservabilityRepository for local development and unit tests. Requires no Azure
or Cosmos DB connectivity — the default provider, mirroring
src.services.conversation_store.in_memory's existing pattern.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from src.domain.observability import ConversationSummary, RunRecord, SummaryKpis
from src.domain.observability_repository import ObservabilityFilters


class InMemoryObservabilityRepository:
    """ObservabilityRepository backed by in-process dicts. Not intended for production use —
    state is lost on process restart, same caveat as InMemoryConversationRepository."""

    def __init__(self) -> None:
        self._runs: dict[str, RunRecord] = {}
        self._runs_by_conversation: dict[str, list[str]] = {}
        self._summaries: dict[str, ConversationSummary] = {}

    async def record_run(self, run: RunRecord) -> None:
        self._runs[run.run_id] = run.model_copy(deep=True)
        self._runs_by_conversation.setdefault(run.conversation_id, []).append(run.run_id)

        summary = self._summaries.get(run.conversation_id)
        now = datetime.now(UTC)
        input_tokens = run.token_usage.prompt_tokens if run.token_usage else 0
        output_tokens = run.token_usage.completion_tokens if run.token_usage else 0
        cost = run.estimated_cost_usd or 0.0
        if summary is None:
            self._summaries[run.conversation_id] = ConversationSummary(
                id=run.conversation_id,
                conversation_id=run.conversation_id,
                user_id=run.user_id,
                created_at=run.created_at,
                updated_at=now,
                primary_domain=run.selected_agent,
                run_count=1,
                total_input_tokens=input_tokens,
                total_output_tokens=output_tokens,
                total_estimated_cost_usd=cost,
                business_outcome=run.final_status,
            )
            return

        self._summaries[run.conversation_id] = summary.model_copy(
            update={
                "updated_at": now,
                "primary_domain": run.selected_agent or summary.primary_domain,
                "run_count": summary.run_count + 1,
                "total_input_tokens": summary.total_input_tokens + input_tokens,
                "total_output_tokens": summary.total_output_tokens + output_tokens,
                "total_estimated_cost_usd": summary.total_estimated_cost_usd + cost,
                "business_outcome": run.final_status or summary.business_outcome,
            }
        )

    async def get_run(self, run_id: str) -> RunRecord | None:
        run = self._runs.get(run_id)
        return run.model_copy(deep=True) if run else None

    async def list_runs_for_conversation(self, conversation_id: str) -> list[RunRecord]:
        run_ids = self._runs_by_conversation.get(conversation_id, [])
        runs = [self._runs[run_id] for run_id in run_ids if run_id in self._runs]
        runs.sort(key=lambda r: r.created_at)
        return [run.model_copy(deep=True) for run in runs]

    async def get_conversation_summary(self, conversation_id: str) -> ConversationSummary | None:
        summary = self._summaries.get(conversation_id)
        return summary.model_copy(deep=True) if summary else None

    async def list_conversation_summaries(
        self,
        filters: ObservabilityFilters,
        *,
        skip: int,
        limit: int,
        sort: Literal["updated_desc", "updated_asc", "cost_desc"] = "updated_desc",
    ) -> tuple[list[ConversationSummary], int]:
        matches = [s for s in self._summaries.values() if _matches(s, filters)]
        if sort == "updated_desc":
            matches.sort(key=lambda s: s.updated_at, reverse=True)
        elif sort == "updated_asc":
            matches.sort(key=lambda s: s.updated_at)
        elif sort == "cost_desc":
            matches.sort(key=lambda s: s.total_estimated_cost_usd, reverse=True)
        total = len(matches)
        page = matches[skip : skip + limit]
        return [s.model_copy(deep=True) for s in page], total

    async def get_summary_kpis(self, filters: ObservabilityFilters) -> SummaryKpis:
        matches = [s for s in self._summaries.values() if _matches(s, filters)]
        conversation_ids = {s.conversation_id for s in matches}
        runs = [
            run
            for run in self._runs.values()
            if run.conversation_id in conversation_ids
        ]
        if not runs:
            return SummaryKpis(
                conversation_count=len(matches),
                run_count=0,
                total_input_tokens=sum(s.total_input_tokens for s in matches),
                total_output_tokens=sum(s.total_output_tokens for s in matches),
                total_estimated_cost_usd=sum(s.total_estimated_cost_usd for s in matches),
            )
        succeeded = sum(1 for r in runs if r.final_status == "completed")
        latencies = [r.total_latency_ms for r in runs if r.total_latency_ms is not None]
        return SummaryKpis(
            conversation_count=len(matches),
            run_count=len(runs),
            success_rate=succeeded / len(runs) if runs else None,
            average_latency_ms=(sum(latencies) / len(latencies)) if latencies else None,
            total_input_tokens=sum(s.total_input_tokens for s in matches),
            total_output_tokens=sum(s.total_output_tokens for s in matches),
            total_estimated_cost_usd=sum(s.total_estimated_cost_usd for s in matches),
        )


def _matches(summary: ConversationSummary, filters: ObservabilityFilters) -> bool:
    if filters.user_id and summary.user_id != filters.user_id:
        return False
    if filters.agent and summary.primary_domain != filters.agent:
        return False
    if filters.status and summary.business_outcome != filters.status:
        return False
    if filters.search:
        needle = filters.search.lower()
        haystack = " ".join(
            filter(
                None,
                [summary.conversation_id, summary.user_id, summary.last_message_preview],
            )
        ).lower()
        if needle not in haystack:
            return False
    return True

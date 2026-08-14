"""Abstract contract for business/agentic observability persistence. Concrete adapters live
under src/services/observability_store/ (in-memory for local dev/tests, Cosmos DB for Azure),
mirroring src.domain.conversation_repository's existing pattern exactly.

Entirely separate from ConversationRepository (src/domain/conversation_repository.py) — this
repository never reads or writes the `conversations` container, so the core chat persistence
path is never touched by this feature (PBI-13-01).
"""

from __future__ import annotations

from typing import Literal, Protocol

from src.domain.observability import ConversationSummary, RunRecord, SummaryKpis


class ObservabilityFilters:
    """Plain filter parameters shared by list_conversation_summaries and summary_kpis. Not a
    Pydantic model: constructed internally by the API layer from validated query parameters,
    never deserialized from a raw request body."""

    def __init__(
        self,
        *,
        user_id: str | None = None,
        agent: str | None = None,
        status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        search: str | None = None,
    ) -> None:
        self.user_id = user_id
        self.agent = agent
        self.status = status
        self.date_from = date_from
        self.date_to = date_to
        self.search = search


class ObservabilityRepository(Protocol):
    """Persistence contract for run telemetry and conversation-level observability aggregates."""

    async def record_run(self, run: RunRecord) -> None:
        """Persist one RunRecord and increment its conversation's ConversationSummary
        aggregates (run_count, token/cost totals) — creating the summary if this is the
        conversation's first recorded run. Best-effort from the caller's perspective: the
        caller (ObservabilityService) is responsible for ensuring a raised exception here never
        propagates into the chat request path."""
        ...

    async def get_run(self, run_id: str) -> RunRecord | None:
        """Point lookup of one run by id, regardless of which conversation it belongs to."""
        ...

    async def list_runs_for_conversation(self, conversation_id: str) -> list[RunRecord]:
        """List every run recorded for one conversation, oldest first."""
        ...

    async def get_conversation_summary(self, conversation_id: str) -> ConversationSummary | None:
        ...

    async def list_conversation_summaries(
        self,
        filters: ObservabilityFilters,
        *,
        skip: int,
        limit: int,
        sort: Literal["updated_desc", "updated_asc", "cost_desc"] = "updated_desc",
    ) -> tuple[list[ConversationSummary], int]:
        """Server-side paginated, filtered list for the dashboard's conversation table. Returns
        (page_items, total_matching_count). Never retrieves every conversation in one request
        (PBI-13-01 §10)."""
        ...

    async def get_summary_kpis(self, filters: ObservabilityFilters) -> SummaryKpis:
        """Aggregate KPIs for the dashboard's top strip, respecting the same filters as
        list_conversation_summaries."""
        ...

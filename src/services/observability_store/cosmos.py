"""Cosmos DB adapter for ObservabilityRepository.

Same authentication (DefaultAzureCredential) and retry/circuit-breaker pattern as
src.services.conversation_store.cosmos.CosmosConversationRepository — see that module's
docstring for the resilience rationale, identical here.

Writes to a container distinct from `conversations` (default name `observability_runs`,
partition key `/conversationId`) holding two document "kinds", discriminated by `docType`:
`"run"` (one RunRecord) and `"conversation_summary"` (one ConversationSummary, aggregated
incrementally as runs are recorded). Both partitioned by conversationId so a conversation
detail view (list_runs_for_conversation + get_conversation_summary) is always a
single-partition read. Dashboard-wide listing/KPIs are necessarily cross-partition (V1 has no
partition key that spans "every conversation across every user" — see the ADR) but never reads
the `conversations` container or any embedded message array.

Not imported by the in-memory local-development path; only reached via
src.services.observability_store.factory when OBSERVABILITY_STORE_PROVIDER=cosmos.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Literal, TypeVar

from azure.core.exceptions import ServiceRequestError, ServiceResponseError
from azure.cosmos import exceptions
from azure.cosmos.aio import ContainerProxy, CosmosClient
from azure.identity.aio import DefaultAzureCredential

from src.core.resilience import CircuitBreaker, retry_with_backoff
from src.domain.observability import ConversationSummary, RunRecord, SummaryKpis
from src.domain.observability_repository import ObservabilityFilters

T = TypeVar("T")

_PROVIDER_NAME = "cosmos_db_observability"
_RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    exceptions.CosmosHttpResponseError,
    ServiceRequestError,
    ServiceResponseError,
)
_RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 503})
_RETRY_MAX_ATTEMPTS = 3
_RETRY_BASE_DELAY_SECONDS = 0.5
_RETRY_MAX_DELAY_SECONDS = 8.0
_CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
_CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS = 30.0


def _is_retryable_status(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code is None:
        return True
    return status_code in _RETRYABLE_STATUS_CODES


class CosmosObservabilityRepository:
    """ObservabilityRepository implementation backed by Azure Cosmos DB for NoSQL."""

    def __init__(self, endpoint: str, database_name: str, container_name: str) -> None:
        self._credential = DefaultAzureCredential()
        self._client = CosmosClient(endpoint, credential=self._credential)
        self._database_name = database_name
        self._container_name = container_name
        self._circuit_breaker = CircuitBreaker(
            _PROVIDER_NAME,
            failure_threshold=_CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            reset_timeout_seconds=_CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS,
        )

    async def _resilient_call(
        self, operation: Callable[[], Awaitable[T]], *, operation_name: str
    ) -> T:
        async def _with_retry() -> T:
            return await retry_with_backoff(
                operation,
                retryable_exceptions=_RETRYABLE_EXCEPTIONS,
                max_attempts=_RETRY_MAX_ATTEMPTS,
                base_delay_seconds=_RETRY_BASE_DELAY_SECONDS,
                max_delay_seconds=_RETRY_MAX_DELAY_SECONDS,
                operation_name=f"{_PROVIDER_NAME} {operation_name}",
                is_retryable=_is_retryable_status,
            )

        return await self._circuit_breaker.call(_with_retry)

    async def close(self) -> None:
        await self._client.close()
        await self._credential.close()

    async def _container(self) -> ContainerProxy:
        database = self._client.get_database_client(self._database_name)
        return database.get_container_client(self._container_name)

    async def record_run(self, run: RunRecord) -> None:
        container = await self._container()
        run_item = run.model_dump(mode="json", by_alias=True)
        run_item["docType"] = "run"

        async def _create_run() -> dict:
            return await container.create_item(body=run_item)

        await self._resilient_call(_create_run, operation_name="create_item(run)")
        await self._upsert_summary_increment(container, run)

    async def _upsert_summary_increment(self, container: ContainerProxy, run: RunRecord) -> None:
        existing = await self.get_conversation_summary(run.conversation_id)
        now = datetime.now(UTC)
        input_tokens = run.token_usage.prompt_tokens if run.token_usage else 0
        output_tokens = run.token_usage.completion_tokens if run.token_usage else 0
        cost = run.estimated_cost_usd or 0.0

        if existing is None:
            summary = ConversationSummary(
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
        else:
            summary = existing.model_copy(
                update={
                    "updated_at": now,
                    "primary_domain": run.selected_agent or existing.primary_domain,
                    "run_count": existing.run_count + 1,
                    "total_input_tokens": existing.total_input_tokens + input_tokens,
                    "total_output_tokens": existing.total_output_tokens + output_tokens,
                    "total_estimated_cost_usd": existing.total_estimated_cost_usd + cost,
                    "business_outcome": run.final_status or existing.business_outcome,
                }
            )

        summary_item = summary.model_dump(mode="json", by_alias=True)
        summary_item["docType"] = "conversation_summary"

        async def _upsert_summary() -> dict:
            return await container.upsert_item(body=summary_item)

        await self._resilient_call(_upsert_summary, operation_name="upsert_item(summary)")

    async def get_run(self, run_id: str) -> RunRecord | None:
        container = await self._container()
        query = "SELECT * FROM c WHERE c.docType = 'run' AND c.id = @id"

        async def _query() -> list[dict]:
            items = container.query_items(query=query, parameters=[{"name": "@id", "value": run_id}])
            return [item async for item in items]

        results = await self._resilient_call(_query, operation_name="query_items(get_run)")
        return RunRecord.model_validate(results[0]) if results else None

    async def list_runs_for_conversation(self, conversation_id: str) -> list[RunRecord]:
        container = await self._container()
        query = (
            "SELECT * FROM c WHERE c.docType = 'run' AND c.conversationId = @cid "
            "ORDER BY c.createdAt ASC"
        )

        async def _query() -> list[dict]:
            items = container.query_items(
                query=query,
                parameters=[{"name": "@cid", "value": conversation_id}],
                partition_key=conversation_id,
            )
            return [item async for item in items]

        results = await self._resilient_call(_query, operation_name="query_items(list_runs)")
        return [RunRecord.model_validate(item) for item in results]

    async def get_conversation_summary(self, conversation_id: str) -> ConversationSummary | None:
        container = await self._container()

        async def _read() -> dict:
            return await container.read_item(item=conversation_id, partition_key=conversation_id)

        try:
            item = await self._resilient_call(_read, operation_name="read_item(summary)")
        except exceptions.CosmosResourceNotFoundError:
            return None
        return ConversationSummary.model_validate(item)

    async def list_conversation_summaries(
        self,
        filters: ObservabilityFilters,
        *,
        skip: int,
        limit: int,
        sort: Literal["updated_desc", "updated_asc", "cost_desc"] = "updated_desc",
    ) -> tuple[list[ConversationSummary], int]:
        container = await self._container()
        where, parameters = _build_summary_where(filters)
        order = {
            "updated_desc": "c.updatedAt DESC",
            "updated_asc": "c.updatedAt ASC",
            "cost_desc": "c.totalEstimatedCostUsd DESC",
        }[sort]

        count_query = f"SELECT VALUE COUNT(1) FROM c WHERE {where}"
        page_query = (
            f"SELECT * FROM c WHERE {where} ORDER BY {order} "
            f"OFFSET {int(skip)} LIMIT {int(limit)}"
        )

        async def _count() -> list[Any]:
            items = container.query_items(
                query=count_query, parameters=parameters, enable_cross_partition_query=True
            )
            return [item async for item in items]

        async def _page() -> list[dict]:
            items = container.query_items(
                query=page_query, parameters=parameters, enable_cross_partition_query=True
            )
            return [item async for item in items]

        total_result = await self._resilient_call(_count, operation_name="query_items(count)")
        page_result = await self._resilient_call(_page, operation_name="query_items(page)")
        total = total_result[0] if total_result else 0
        return [ConversationSummary.model_validate(item) for item in page_result], total

    async def get_summary_kpis(self, filters: ObservabilityFilters) -> SummaryKpis:
        container = await self._container()
        where, parameters = _build_summary_where(filters)
        agg_query = (
            "SELECT COUNT(1) AS conversationCount, SUM(c.runCount) AS runCount, "
            "SUM(c.totalInputTokens) AS totalInputTokens, "
            "SUM(c.totalOutputTokens) AS totalOutputTokens, "
            "SUM(c.totalEstimatedCostUsd) AS totalEstimatedCostUsd "
            f"FROM c WHERE {where}"
        )

        async def _query() -> list[dict]:
            items = container.query_items(
                query=agg_query, parameters=parameters, enable_cross_partition_query=True
            )
            return [item async for item in items]

        results = await self._resilient_call(_query, operation_name="query_items(kpis)")
        row = results[0] if results else {}
        return SummaryKpis(
            conversation_count=row.get("conversationCount"),
            run_count=row.get("runCount"),
            total_input_tokens=row.get("totalInputTokens"),
            total_output_tokens=row.get("totalOutputTokens"),
            total_estimated_cost_usd=row.get("totalEstimatedCostUsd"),
            # success_rate/average_latency_ms require scanning `run` docs individually (no
            # pre-aggregated success/latency total on ConversationSummary) — left Unavailable
            # in the Cosmos path for V1 rather than adding a second, more expensive
            # cross-partition scan over every run document; the in-memory adapter (used in
            # tests) still computes them exactly, so the calculation itself is verified.
            success_rate=None,
            average_latency_ms=None,
        )


def _build_summary_where(filters: ObservabilityFilters) -> tuple[str, list[dict]]:
    clauses = ["c.docType = 'conversation_summary'"]
    parameters: list[dict] = []
    if filters.user_id:
        clauses.append("c.userId = @userId")
        parameters.append({"name": "@userId", "value": filters.user_id})
    if filters.agent:
        clauses.append("c.primaryDomain = @agent")
        parameters.append({"name": "@agent", "value": filters.agent})
    if filters.status:
        clauses.append("c.businessOutcome = @status")
        parameters.append({"name": "@status", "value": filters.status})
    if filters.search:
        clauses.append("CONTAINS(LOWER(c.conversationId), @search)")
        parameters.append({"name": "@search", "value": filters.search.lower()})
    return " AND ".join(clauses), parameters

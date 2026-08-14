"""Unit tests for InMemoryObservabilityRepository (PBI-13-01): pagination, filters, aggregate
increments, and that a tid:oid-shaped user_id flows through untouched (never re-parsed/altered).
"""

from datetime import UTC, datetime

import pytest

from src.domain.observability import RunRecord
from src.domain.observability_repository import ObservabilityFilters
from src.services.observability_store.in_memory import InMemoryObservabilityRepository


def _run(run_id: str, conversation_id: str, user_id: str, **overrides) -> RunRecord:
    defaults = {
        "id": run_id,
        "run_id": run_id,
        "conversation_id": conversation_id,
        "user_id": user_id,
        "created_at": datetime.now(UTC),
        "selected_agent": "ClaimsAgent",
        "final_status": "completed",
    }
    defaults.update(overrides)
    return RunRecord(**defaults)


async def test_record_run_creates_and_increments_conversation_summary() -> None:
    repository = InMemoryObservabilityRepository()

    await repository.record_run(_run("run-1", "conv-1", "tid-a:oid-a"))
    await repository.record_run(_run("run-2", "conv-1", "tid-a:oid-a"))

    summary = await repository.get_conversation_summary("conv-1")
    assert summary is not None
    assert summary.run_count == 2
    # The tid:oid identity is stored verbatim, never split/reformatted.
    assert summary.user_id == "tid-a:oid-a"


async def test_list_runs_for_conversation_returns_oldest_first() -> None:
    repository = InMemoryObservabilityRepository()
    await repository.record_run(_run("run-2", "conv-1", "u1", created_at=datetime(2026, 1, 2, tzinfo=UTC)))
    await repository.record_run(_run("run-1", "conv-1", "u1", created_at=datetime(2026, 1, 1, tzinfo=UTC)))

    runs = await repository.list_runs_for_conversation("conv-1")

    assert [r.run_id for r in runs] == ["run-1", "run-2"]


async def test_get_run_is_findable_regardless_of_conversation() -> None:
    repository = InMemoryObservabilityRepository()
    await repository.record_run(_run("run-1", "conv-1", "u1"))

    run = await repository.get_run("run-1")

    assert run is not None
    assert run.conversation_id == "conv-1"


async def test_get_run_returns_none_for_an_unknown_run() -> None:
    repository = InMemoryObservabilityRepository()

    assert await repository.get_run("does-not-exist") is None


async def test_list_conversation_summaries_paginates_server_side() -> None:
    repository = InMemoryObservabilityRepository()
    for i in range(5):
        await repository.record_run(_run(f"run-{i}", f"conv-{i}", "u1"))

    page1, total = await repository.list_conversation_summaries(
        ObservabilityFilters(), skip=0, limit=2
    )
    page2, _total = await repository.list_conversation_summaries(
        ObservabilityFilters(), skip=2, limit=2
    )

    assert total == 5
    assert len(page1) == 2
    assert len(page2) == 2
    assert {s.conversation_id for s in page1}.isdisjoint({s.conversation_id for s in page2})


async def test_list_conversation_summaries_filters_by_user_id() -> None:
    repository = InMemoryObservabilityRepository()
    await repository.record_run(_run("run-1", "conv-1", "tid-a:oid-a"))
    await repository.record_run(_run("run-2", "conv-2", "tid-b:oid-b"))

    items, total = await repository.list_conversation_summaries(
        ObservabilityFilters(user_id="tid-a:oid-a"), skip=0, limit=10
    )

    assert total == 1
    assert items[0].conversation_id == "conv-1"


async def test_get_summary_kpis_computes_success_rate_and_totals() -> None:
    repository = InMemoryObservabilityRepository()
    await repository.record_run(_run("run-1", "conv-1", "u1", final_status="completed", total_latency_ms=100.0))
    await repository.record_run(_run("run-2", "conv-1", "u1", final_status="error", total_latency_ms=200.0))

    kpis = await repository.get_summary_kpis(ObservabilityFilters())

    assert kpis.run_count == 2
    assert kpis.success_rate == pytest.approx(0.5)
    assert kpis.average_latency_ms == pytest.approx(150.0)


async def test_get_summary_kpis_conversation_count_is_never_fabricated_when_empty() -> None:
    repository = InMemoryObservabilityRepository()

    kpis = await repository.get_summary_kpis(ObservabilityFilters())

    assert kpis.conversation_count == 0
    assert kpis.success_rate is None
    assert kpis.average_latency_ms is None

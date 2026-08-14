"""Unit tests for src.observability.service.ObservabilityService (PBI-13-01 §3/§8).

Covers: telemetry persistence failure never raises (best-effort, non-blocking), a RunRecord
never carries raw LLM reasoning/chain-of-thought text (only structured fields exist to hold
anything at all), and tool-call latency correlation from ReAct events.
"""

from datetime import UTC, datetime

import pytest

from src.core.tool_calling.models import LLMUsageTotal, ReActEvent, ToolCallResult
from src.observability.pricing import PricingCatalog
from src.observability.service import ObservabilityService
from src.services.observability_store.in_memory import InMemoryObservabilityRepository
from src.supervisor.models import AgentResponse, IntentCategory


class _RaisingObservabilityRepository:
    async def record_run(self, run):
        raise RuntimeError("Cosmos is unreachable")

    async def get_run(self, run_id):
        raise NotImplementedError

    async def list_runs_for_conversation(self, conversation_id):
        raise NotImplementedError

    async def get_conversation_summary(self, conversation_id):
        raise NotImplementedError

    async def list_conversation_summaries(self, filters, *, skip, limit, sort="updated_desc"):
        raise NotImplementedError

    async def get_summary_kpis(self, filters):
        raise NotImplementedError


@pytest.fixture
def empty_pricing_catalog(tmp_path) -> PricingCatalog:
    path = tmp_path / "pricing.json"
    path.write_text('{"catalogVersion": "test", "entries": []}', encoding="utf-8")
    return PricingCatalog(path)


async def test_record_run_never_raises_when_the_repository_fails(empty_pricing_catalog) -> None:
    service = ObservabilityService(
        repository=_RaisingObservabilityRepository(), pricing_catalog=empty_pricing_catalog
    )

    await service.record_run(
        run_id="run-1",
        conversation_id="conv-1",
        message_id="msg-1",
        trace_id="corr-1",
        user_id="tid:oid",
        started_at=datetime.now(UTC),
        total_latency_ms=42.0,
        detected_intent="CLAIMS",
        agent_response=AgentResponse(
            conversation_id="conv-1", agent="ClaimsAgent", intent=IntentCategory.CLAIMS, response="ok"
        ),
        react_events=[],
    )
    # No exception means telemetry failure did not propagate — the assertion is that we got here.


async def test_record_run_persists_a_run_and_it_is_readable_back(empty_pricing_catalog) -> None:
    repository = InMemoryObservabilityRepository()
    service = ObservabilityService(repository=repository, pricing_catalog=empty_pricing_catalog)

    agent_response = AgentResponse(
        conversation_id="conv-1",
        agent="ClaimsAgent",
        intent=IntentCategory.CLAIMS,
        response="ok",
        tool_calls=[
            ToolCallResult(call_id="call-1", tool_name="policy_lookup", success=True, data={"a": 1})
        ],
        model="gpt-5-mini",
        token_usage=LLMUsageTotal(prompt_tokens=100, completion_tokens=50, total_tokens=150),
    )
    events = [
        ReActEvent(event_type="reasoning_iteration_started", iteration=1),
        ReActEvent(event_type="tool_executed", iteration=1, tool_name="policy_lookup", success=True, latency_ms=12.5),
        ReActEvent(event_type="final_answer_reached", iteration=1),
    ]

    await service.record_run(
        run_id="run-1",
        conversation_id="conv-1",
        message_id="msg-1",
        trace_id="corr-1",
        user_id="tid:oid",
        started_at=datetime.now(UTC),
        total_latency_ms=42.0,
        detected_intent="CLAIMS",
        agent_response=agent_response,
        react_events=events,
    )

    run = await service.get_run("run-1")
    assert run is not None
    assert run.conversation_id == "conv-1"
    assert run.final_status == "completed"
    assert run.tool_calls[0].latency_ms == 12.5
    assert run.token_usage is not None
    assert run.token_usage.prompt_tokens == 100

    summary = await service.get_conversation_summary("conv-1")
    assert summary is not None
    assert summary.run_count == 1
    assert summary.total_input_tokens == 100


def test_run_record_has_no_field_capable_of_holding_reasoning_text() -> None:
    """CLAUDE.md §10 / PBI-13-01 §8: structural guarantee, not a runtime filter — assert the
    RunRecord/RunToolCall schemas simply have no field named anything reasoning-shaped."""
    from src.domain.observability import RunRecord, RunToolCall

    forbidden_substrings = ("reasoning", "thought", "chain_of_thought", "prompt")
    for model in (RunRecord, RunToolCall):
        for field_name in model.model_fields:
            lowered = field_name.lower()
            assert not any(bad in lowered for bad in forbidden_substrings), (
                f"{model.__name__}.{field_name} looks reasoning-shaped"
            )


async def test_react_event_never_carries_free_text_reasoning_content() -> None:
    """ReActEvent's own schema has no text/content field — only structural metadata (event
    type, iteration, tool name, success, latency, timestamp)."""
    for field_name in ReActEvent.model_fields:
        assert field_name not in {"text", "content", "reasoning", "prompt"}

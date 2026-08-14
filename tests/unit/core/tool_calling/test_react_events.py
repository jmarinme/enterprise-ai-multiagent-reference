"""Unit tests for ToolCallingOrchestrator's on_event observability hook (PBI-13-01 §8):
best-effort (a raising observer never breaks the loop), fires the expected lifecycle events,
and usage/model accumulate onto ToolCallingResponse — all purely additive to the existing ReAct
loop tested in test_tool_calling_orchestrator.py.
"""

from __future__ import annotations

from src.core.tool_calling.models import ReActEvent, ToolCallingContext
from src.core.tool_calling.orchestrator import ToolCallingOrchestrator
from src.llm.models import LLMMessage, LLMMessageRole, LLMResponse, LLMUsage, ToolCallArgument
from src.llm.models import ToolCallRequest as LLMToolCallRequest
from src.services.tools.policy_lookup_tool import PolicyLookupTool
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry, ToolRegistry


class _ScriptedLLMProvider:
    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)

    async def generate(self, request) -> LLMResponse:
        return self._responses.pop(0)


def _build_registry() -> ToolRegistry:
    registry = InMemoryToolRegistry()
    registry.register(PolicyLookupTool())
    return registry


def _build_orchestrator(registry: ToolRegistry, llm_provider: object) -> ToolCallingOrchestrator:
    return ToolCallingOrchestrator(
        tool_registry=registry,
        tool_executor=ToolExecutor(tool_registry=registry),
        llm_provider=llm_provider,  # type: ignore[arg-type]
    )


def _user_message() -> list[LLMMessage]:
    return [LLMMessage(role=LLMMessageRole.USER, content="hello")]


async def test_on_event_fires_tool_lifecycle_events_in_order() -> None:
    registry = _build_registry()
    provider = _ScriptedLLMProvider(
        [
            LLMResponse(
                text="",
                model="stub-model",
                usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
                tool_calls=[
                    LLMToolCallRequest(
                        call_id="call-1",
                        tool_name="policy_lookup",
                        arguments=[ToolCallArgument(name="policy_number", value="SYN-POL-0001")],
                    )
                ],
            ),
            LLMResponse(
                text="done",
                model="stub-model",
                usage=LLMUsage(prompt_tokens=8, completion_tokens=2, total_tokens=10),
            ),
        ]
    )
    orchestrator = _build_orchestrator(registry, provider)
    events: list[ReActEvent] = []

    response = await orchestrator.run(
        messages=_user_message(),
        context=ToolCallingContext(agent_name="TestAgent", allowed_tools=["policy_lookup"]),
        on_event=events.append,
    )

    event_types = [e.event_type for e in events]
    assert event_types == [
        "reasoning_iteration_started",
        "tool_required",
        "tool_selected",
        "tool_executed",
        "reasoning_iteration_started",
        "final_answer_reached",
    ]
    tool_executed = next(e for e in events if e.event_type == "tool_executed")
    assert tool_executed.tool_name == "policy_lookup"
    assert tool_executed.success is True
    assert tool_executed.latency_ms is not None

    # Usage/model accumulate across both LLM calls (PBI-13-01 additions to ToolCallingResponse).
    assert response.model == "stub-model"
    assert response.usage.prompt_tokens == 18
    assert response.usage.completion_tokens == 7


async def test_a_raising_on_event_observer_never_breaks_the_loop() -> None:
    registry = _build_registry()
    provider = _ScriptedLLMProvider([LLMResponse(text="final answer", model="stub")])
    orchestrator = _build_orchestrator(registry, provider)

    def _raising_observer(_event: ReActEvent) -> None:
        raise RuntimeError("observer boom")

    response = await orchestrator.run(
        messages=_user_message(),
        context=ToolCallingContext(agent_name="TestAgent", allowed_tools=["policy_lookup"]),
        on_event=_raising_observer,
    )

    assert response.text == "final answer"


async def test_on_event_is_optional_and_defaults_to_none() -> None:
    """Every prior caller (before PBI-13-01) never passed on_event — this must still work."""
    registry = _build_registry()
    provider = _ScriptedLLMProvider([LLMResponse(text="final answer", model="stub")])
    orchestrator = _build_orchestrator(registry, provider)

    response = await orchestrator.run(
        messages=_user_message(),
        context=ToolCallingContext(agent_name="TestAgent", allowed_tools=["policy_lookup"]),
    )

    assert response.text == "final answer"


async def test_react_event_fields_never_include_llm_message_text() -> None:
    """Structural proof, not just an assertion on this run's output: ReActEvent has no field
    that could ever be assigned the LLM's actual text/reasoning content."""
    assert set(ReActEvent.model_fields) == {
        "event_type",
        "iteration",
        "tool_name",
        "success",
        "latency_ms",
        "timestamp",
    }

"""Unit tests for ToolCallingOrchestrator (PBI-02-04): tool definition generation, allowed/
unauthorized/unknown tool calls, malformed arguments, Tool validation/execution failure,
multiple sequential tool calls, maximum iteration protection, and context propagation.

Every LLM-facing behavior is driven by a scripted test-double LLMProvider (never MockLLMProvider
itself) so each edge case is exercised deterministically and independently of MockLLMProvider's
own cooperative tool-calling behavior (tested separately in tests/unit/llm/test_mock_provider.py).
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from src.core.tool_calling.exceptions import ToolCallingError
from src.core.tool_calling.models import ToolCallingContext
from src.core.tool_calling.orchestrator import ToolCallingOrchestrator
from src.llm.models import (
    LLMMessage,
    LLMMessageRole,
    LLMRequest,
    LLMResponse,
    ToolCallArgument,
    ToolCallRequest,
)
from src.services.tools.payment_status_tool import PaymentStatusTool
from src.services.tools.policy_lookup_tool import PolicyLookupTool
from src.tools.executor import ToolExecutor
from src.tools.models import ToolExecutionContext, ToolResult
from src.tools.registry import InMemoryToolRegistry, ToolRegistry


class _RecordingToolInput(BaseModel):
    value: str


class _FailingTool:
    name = "always_fails"
    description = "A tool that always raises during execution."
    version = "1.0.0"
    input_model = _RecordingToolInput

    async def execute(
        self, tool_input: _RecordingToolInput, context: ToolExecutionContext
    ) -> ToolResult[Any]:
        raise RuntimeError("simulated failure")


class _RecordingTool:
    """Records the ToolExecutionContext each call received, to prove context propagation."""

    name = "recording_tool"
    description = "Records the ToolExecutionContext it receives."
    version = "1.0.0"
    input_model = _RecordingToolInput

    def __init__(self) -> None:
        self.received_contexts: list[ToolExecutionContext] = []

    async def execute(
        self, tool_input: _RecordingToolInput, context: ToolExecutionContext
    ) -> ToolResult[Any]:
        self.received_contexts.append(context)
        return ToolResult(
            tool_name=self.name, success=True, data=None, correlation_id=context.correlation_id
        )


class _ScriptedLLMProvider:
    """Returns one scripted LLMResponse per call, in order. Records every LLMRequest it saw."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[LLMRequest] = []

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return self._responses.pop(0)


class _AlwaysRequestsToolCallProvider:
    """Never terminates on its own — always requests another tool call, regardless of turn
    count or message history. Used to prove ToolCallingOrchestrator's own max_iterations cap
    is the actual safety net, not cooperative LLM behavior."""

    async def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            text="",
            model="stub",
            tool_calls=[
                ToolCallRequest(
                    call_id=f"call-{len(request.messages)}",
                    tool_name="policy_lookup",
                    arguments=[ToolCallArgument(name="policy_number", value="SYN-POL-0001")],
                )
            ],
        )


def _build_registry(*tools: object) -> ToolRegistry:
    registry = InMemoryToolRegistry()
    for tool in tools:
        registry.register(tool)  # type: ignore[arg-type]
    return registry


def _build_orchestrator(registry: ToolRegistry, llm_provider: object) -> ToolCallingOrchestrator:
    return ToolCallingOrchestrator(
        tool_registry=registry,
        tool_executor=ToolExecutor(tool_registry=registry),
        llm_provider=llm_provider,  # type: ignore[arg-type]
    )


def _user_message(content: str = "hello") -> list[LLMMessage]:
    return [LLMMessage(role=LLMMessageRole.USER, content=content)]


# --- tool definition generation -------------------------------------------------------------


def test_build_tool_definitions_uses_the_tools_own_metadata_and_schema() -> None:
    registry = _build_registry(PolicyLookupTool())
    orchestrator = _build_orchestrator(registry, _ScriptedLLMProvider([]))

    definitions = orchestrator.build_tool_definitions(["policy_lookup"])

    assert len(definitions) == 1
    assert definitions[0].name == "policy_lookup"
    assert definitions[0].description == PolicyLookupTool.description
    assert "policy_number" in definitions[0].parameters_schema["properties"]


def test_build_tool_definitions_raises_for_an_allow_listed_but_unregistered_tool() -> None:
    registry = _build_registry(PolicyLookupTool())
    orchestrator = _build_orchestrator(registry, _ScriptedLLMProvider([]))

    with pytest.raises(ToolCallingError):
        orchestrator.build_tool_definitions(["policy_lookup", "does_not_exist"])


# --- no tool calls requested -----------------------------------------------------------------


async def test_run_with_no_tool_calls_returns_the_llm_text_immediately() -> None:
    registry = _build_registry(PolicyLookupTool())
    llm = _ScriptedLLMProvider([LLMResponse(text="a plain answer", model="stub")])
    orchestrator = _build_orchestrator(registry, llm)
    context = ToolCallingContext(agent_name="ClaimsAgent", allowed_tools=["policy_lookup"])

    response = await orchestrator.run(messages=_user_message(), context=context)

    assert response.text == "a plain answer"
    assert response.tool_calls == []
    assert response.iterations == 1
    assert response.stopped_due_to_max_iterations is False


# --- allowed tool call -------------------------------------------------------------------------


async def test_run_executes_an_allowed_tool_call_and_returns_the_final_response() -> None:
    registry = _build_registry(PolicyLookupTool())
    llm = _ScriptedLLMProvider(
        [
            LLMResponse(
                text="",
                model="stub",
                tool_calls=[
                    ToolCallRequest(
                        call_id="call-1",
                        tool_name="policy_lookup",
                        arguments=[ToolCallArgument(name="policy_number", value="SYN-POL-0001")],
                    )
                ],
            ),
            LLMResponse(text="Here is the policy status.", model="stub"),
        ]
    )
    orchestrator = _build_orchestrator(registry, llm)
    context = ToolCallingContext(agent_name="ClaimsAgent", allowed_tools=["policy_lookup"])

    response = await orchestrator.run(messages=_user_message(), context=context)

    assert response.text == "Here is the policy status."
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool_name == "policy_lookup"
    assert response.tool_calls[0].success is True
    assert response.tool_calls[0].data is not None
    assert response.iterations == 2
    assert response.stopped_due_to_max_iterations is False

    # The tool's result was fed back to the LLM as a TOOL-role message on the second call.
    second_request = llm.requests[1]
    tool_messages = [m for m in second_request.messages if m.role == LLMMessageRole.TOOL]
    assert len(tool_messages) == 1
    assert tool_messages[0].tool_call_id == "call-1"


# --- unauthorized tool call ----------------------------------------------------------------


async def test_run_rejects_an_unauthorized_tool_call_without_executing_it() -> None:
    """policy_lookup is registered but NOT allow-listed for this context — the LLM requesting
    it anyway must be rejected before ToolExecutor is ever invoked."""
    registry = _build_registry(PolicyLookupTool(), PaymentStatusTool())
    llm = _ScriptedLLMProvider(
        [
            LLMResponse(
                text="",
                model="stub",
                tool_calls=[
                    ToolCallRequest(
                        call_id="call-1",
                        tool_name="policy_lookup",
                        arguments=[ToolCallArgument(name="policy_number", value="SYN-POL-0001")],
                    )
                ],
            ),
            LLMResponse(text="done", model="stub"),
        ]
    )
    orchestrator = _build_orchestrator(registry, llm)
    context = ToolCallingContext(agent_name="ClaimsAgent", allowed_tools=["payment_status"])

    response = await orchestrator.run(messages=_user_message(), context=context)

    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].success is False
    assert response.tool_calls[0].error_type == "unauthorized"
    assert response.tool_calls[0].data is None


# --- unknown tool call -----------------------------------------------------------------------


async def test_run_rejects_an_unknown_tool_call_without_executing_it() -> None:
    """A hallucinated tool name — never registered anywhere, not just unauthorized for this
    Agent — must also fail safely, and be distinguishable from "unauthorized"."""
    registry = _build_registry(PolicyLookupTool())
    llm = _ScriptedLLMProvider(
        [
            LLMResponse(
                text="",
                model="stub",
                tool_calls=[
                    ToolCallRequest(call_id="call-1", tool_name="delete_everything", arguments=[])
                ],
            ),
            LLMResponse(text="done", model="stub"),
        ]
    )
    orchestrator = _build_orchestrator(registry, llm)
    context = ToolCallingContext(agent_name="ClaimsAgent", allowed_tools=["policy_lookup"])

    response = await orchestrator.run(messages=_user_message(), context=context)

    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].success is False
    assert response.tool_calls[0].error_type == "unknown_tool"


# --- malformed arguments / Tool validation failure ------------------------------------------


async def test_run_reports_a_tool_failure_for_malformed_arguments_missing_a_required_field() -> (
    None
):
    registry = _build_registry(PolicyLookupTool())
    llm = _ScriptedLLMProvider(
        [
            LLMResponse(
                text="",
                model="stub",
                tool_calls=[
                    ToolCallRequest(call_id="call-1", tool_name="policy_lookup", arguments=[])
                ],
            ),
            LLMResponse(text="done", model="stub"),
        ]
    )
    orchestrator = _build_orchestrator(registry, llm)
    context = ToolCallingContext(agent_name="ClaimsAgent", allowed_tools=["policy_lookup"])

    response = await orchestrator.run(messages=_user_message(), context=context)

    assert response.tool_calls[0].success is False
    assert response.tool_calls[0].error_type == "tool_failed"
    assert "Invalid input for tool" in (response.tool_calls[0].error or "")


async def test_run_reports_a_tool_validation_failure_for_a_wrong_shaped_argument() -> None:
    registry = _build_registry(PolicyLookupTool())
    llm = _ScriptedLLMProvider(
        [
            LLMResponse(
                text="",
                model="stub",
                tool_calls=[
                    ToolCallRequest(
                        call_id="call-1",
                        tool_name="policy_lookup",
                        # policy_number expects a string, not a nested object.
                        arguments=[ToolCallArgument(name="policy_number", value={"nested": True})],
                    )
                ],
            ),
            LLMResponse(text="done", model="stub"),
        ]
    )
    orchestrator = _build_orchestrator(registry, llm)
    context = ToolCallingContext(agent_name="ClaimsAgent", allowed_tools=["policy_lookup"])

    response = await orchestrator.run(messages=_user_message(), context=context)

    assert response.tool_calls[0].success is False
    assert response.tool_calls[0].error_type == "tool_failed"


# --- Tool execution failure ------------------------------------------------------------------


async def test_run_reports_a_tool_execution_failure_without_a_stack_trace() -> None:
    registry = _build_registry(_FailingTool())
    llm = _ScriptedLLMProvider(
        [
            LLMResponse(
                text="",
                model="stub",
                tool_calls=[
                    ToolCallRequest(
                        call_id="call-1",
                        tool_name="always_fails",
                        arguments=[ToolCallArgument(name="value", value="x")],
                    )
                ],
            ),
            LLMResponse(text="done", model="stub"),
        ]
    )
    orchestrator = _build_orchestrator(registry, llm)
    context = ToolCallingContext(agent_name="ClaimsAgent", allowed_tools=["always_fails"])

    response = await orchestrator.run(messages=_user_message(), context=context)

    assert response.tool_calls[0].success is False
    assert response.tool_calls[0].error_type == "tool_failed"
    assert "Traceback" not in (response.tool_calls[0].error or "")


# --- multiple sequential tool calls ----------------------------------------------------------


async def test_run_executes_multiple_tool_calls_within_a_single_llm_turn() -> None:
    registry = _build_registry(PolicyLookupTool(), PaymentStatusTool())
    llm = _ScriptedLLMProvider(
        [
            LLMResponse(
                text="",
                model="stub",
                tool_calls=[
                    ToolCallRequest(
                        call_id="call-1",
                        tool_name="policy_lookup",
                        arguments=[ToolCallArgument(name="policy_number", value="SYN-POL-0001")],
                    ),
                    ToolCallRequest(
                        call_id="call-2",
                        tool_name="payment_status",
                        arguments=[ToolCallArgument(name="policy_number", value="SYN-POL-0001")],
                    ),
                ],
            ),
            LLMResponse(text="Both checks complete.", model="stub"),
        ]
    )
    orchestrator = _build_orchestrator(registry, llm)
    context = ToolCallingContext(
        agent_name="ClaimsAgent", allowed_tools=["policy_lookup", "payment_status"]
    )

    response = await orchestrator.run(messages=_user_message(), context=context)

    assert len(response.tool_calls) == 2
    assert {call.tool_name for call in response.tool_calls} == {"policy_lookup", "payment_status"}
    assert response.iterations == 2


async def test_run_executes_tool_calls_across_multiple_iterations() -> None:
    registry = _build_registry(PolicyLookupTool(), PaymentStatusTool())
    llm = _ScriptedLLMProvider(
        [
            LLMResponse(
                text="",
                model="stub",
                tool_calls=[
                    ToolCallRequest(
                        call_id="call-1",
                        tool_name="policy_lookup",
                        arguments=[ToolCallArgument(name="policy_number", value="SYN-POL-0001")],
                    )
                ],
            ),
            LLMResponse(
                text="",
                model="stub",
                tool_calls=[
                    ToolCallRequest(
                        call_id="call-2",
                        tool_name="payment_status",
                        arguments=[ToolCallArgument(name="policy_number", value="SYN-POL-0001")],
                    )
                ],
            ),
            LLMResponse(text="Sequential checks complete.", model="stub"),
        ]
    )
    orchestrator = _build_orchestrator(registry, llm)
    context = ToolCallingContext(
        agent_name="ClaimsAgent",
        allowed_tools=["policy_lookup", "payment_status"],
        max_iterations=5,
    )

    response = await orchestrator.run(messages=_user_message(), context=context)

    assert response.iterations == 3
    assert [call.tool_name for call in response.tool_calls] == ["policy_lookup", "payment_status"]
    assert response.text == "Sequential checks complete."
    assert response.stopped_due_to_max_iterations is False


# --- maximum iteration protection ------------------------------------------------------------


async def test_run_stops_at_max_iterations_against_a_never_terminating_llm() -> None:
    registry = _build_registry(PolicyLookupTool())
    orchestrator = _build_orchestrator(registry, _AlwaysRequestsToolCallProvider())
    context = ToolCallingContext(
        agent_name="ClaimsAgent", allowed_tools=["policy_lookup"], max_iterations=2
    )

    response = await orchestrator.run(messages=_user_message(), context=context)

    assert response.stopped_due_to_max_iterations is True
    assert response.iterations == 2
    assert len(response.tool_calls) == 2


# --- context propagation -----------------------------------------------------------------------


async def test_run_propagates_correlation_conversation_and_user_ids_to_the_llm_and_the_tool() -> (
    None
):
    recording_tool = _RecordingTool()
    registry = _build_registry(recording_tool)
    llm = _ScriptedLLMProvider(
        [
            LLMResponse(
                text="",
                model="stub",
                tool_calls=[
                    ToolCallRequest(
                        call_id="call-1",
                        tool_name="recording_tool",
                        arguments=[ToolCallArgument(name="value", value="x")],
                    )
                ],
            ),
            LLMResponse(text="done", model="stub"),
        ]
    )
    orchestrator = _build_orchestrator(registry, llm)
    context = ToolCallingContext(
        agent_name="ClaimsAgent",
        allowed_tools=["recording_tool"],
        correlation_id="corr-1",
        conversation_id="conv-1",
        user_id="user-1",
    )

    await orchestrator.run(messages=_user_message(), context=context)

    assert all(
        request.correlation_id == "corr-1"
        and request.conversation_id == "conv-1"
        and request.user_id == "user-1"
        for request in llm.requests
    )
    assert len(recording_tool.received_contexts) == 1
    tool_context = recording_tool.received_contexts[0]
    assert tool_context.correlation_id == "corr-1"
    assert tool_context.conversation_id == "conv-1"
    assert tool_context.user_id == "user-1"

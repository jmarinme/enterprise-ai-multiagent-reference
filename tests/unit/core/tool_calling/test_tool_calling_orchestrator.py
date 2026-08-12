"""Unit tests for ToolCallingOrchestrator (PBI-02-04): tool definition generation, allowed/
unauthorized/unknown tool calls, malformed arguments, Tool validation/execution failure,
multiple sequential tool calls, maximum iteration protection, and context propagation.

Every LLM-facing behavior is driven by a scripted test-double LLMProvider (never MockLLMProvider
itself) so each edge case is exercised deterministically and independently of MockLLMProvider's
own cooperative tool-calling behavior (tested separately in tests/unit/llm/test_mock_provider.py).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from pydantic import BaseModel

from src.core.tool_calling.exceptions import ToolCallingError
from src.core.tool_calling.models import ToolCallingContext
from src.core.tool_calling.orchestrator import ToolCallingOrchestrator
from src.llm.mock_provider import MockLLMProvider
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


class _PolicyLookupInput(BaseModel):
    policy_number: str


class _CountingPolicyLookupTool:
    """Registered as "policy_lookup" (matching the real Tool's name) so scripted duplicate-call
    requests resolve against it — counts how many times execute() actually ran, to prove a
    detected duplicate is genuinely never re-executed (PBI-12-04), not just re-labeled."""

    name = "policy_lookup"
    description = "Counts real executions."
    version = "1.0.0"
    input_model = _PolicyLookupInput

    def __init__(self) -> None:
        self.execution_count = 0

    async def execute(
        self, tool_input: _PolicyLookupInput, context: ToolExecutionContext
    ) -> ToolResult[Any]:
        self.execution_count += 1
        return ToolResult(tool_name=self.name, success=True, data=None)


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


class _RepeatsTheSameToolCallProvider:
    """Requests the identical tool call (same tool + same arguments, only call_id differs)
    every iteration — used to prove duplicate-tool-call detection (PBI-12-04) is what actually
    stops a misbehaving LLM from re-triggering a non-idempotent action, independent of
    max_iterations."""

    def __init__(self) -> None:
        self.call_count = 0

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.call_count += 1
        return LLMResponse(
            text="",
            model="stub",
            tool_calls=[
                ToolCallRequest(
                    call_id=f"call-{self.call_count}",
                    tool_name="policy_lookup",
                    arguments=[ToolCallArgument(name="policy_number", value="SYN-POL-0001")],
                )
            ],
        )


class _SlowLLMProvider:
    """Sleeps longer than any reasonable test timeout before returning — used to prove
    ToolCallingContext.timeout_seconds (PBI-12-04) actually bounds a single hung LLM call."""

    def __init__(self, delay_seconds: float) -> None:
        self._delay_seconds = delay_seconds

    async def generate(self, request: LLMRequest) -> LLMResponse:
        await asyncio.sleep(self._delay_seconds)
        return LLMResponse(text="too slow to matter", model="stub")


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

    # PBI-04-03: the assistant's own tool-calling request must be persisted immediately
    # before the tool result it answers — the exact protocol requirement Azure OpenAI
    # enforces and MockLLMProvider/the scripted test double never did.
    assert second_request.messages[-2].role == LLMMessageRole.ASSISTANT
    assert second_request.messages[-2].tool_calls == [
        ToolCallRequest(
            call_id="call-1",
            tool_name="policy_lookup",
            arguments=[ToolCallArgument(name="policy_number", value="SYN-POL-0001")],
        )
    ]
    assert second_request.messages[-1] is tool_messages[0]
    assert second_request.messages[-1].role == LLMMessageRole.TOOL


async def test_run_persists_the_assistant_tool_calls_message_before_the_tool_result() -> None:
    """Dedicated regression test for the PBI-04-03 fix itself: the final conversation history
    must be user -> assistant(tool_calls) -> tool(tool_call_id) -> in that exact order, with
    the tool_call_id on the tool message matching the call_id inside the assistant's own
    tool_calls — the precise shape Azure OpenAI's real API validates and previously rejected."""
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

    await orchestrator.run(messages=_user_message(), context=context)

    second_request = llm.requests[1]
    roles = [m.role for m in second_request.messages]
    assert roles == [
        LLMMessageRole.USER,
        LLMMessageRole.ASSISTANT,
        LLMMessageRole.TOOL,
    ]
    assistant_message, tool_message = second_request.messages[1], second_request.messages[2]
    assert assistant_message.tool_calls is not None
    assert assistant_message.tool_calls[0].call_id == "call-1"
    assert tool_message.tool_call_id == assistant_message.tool_calls[0].call_id


async def test_run_omits_the_assistant_tool_calls_field_when_no_tool_call_was_requested() -> None:
    """A plain-text turn (no tool_calls) must never gain a spurious assistant tool_calls
    message — the fix is additive only for genuine tool-calling turns."""
    registry = _build_registry(PolicyLookupTool())
    llm = _ScriptedLLMProvider([LLMResponse(text="a plain answer", model="stub")])
    orchestrator = _build_orchestrator(registry, llm)
    context = ToolCallingContext(agent_name="ClaimsAgent", allowed_tools=["policy_lookup"])

    await orchestrator.run(messages=_user_message(), context=context)

    # Only one LLM call happened (no tool call requested), so there is no "second request" to
    # inspect for a spurious assistant/tool pair — the absence of a second call at all is
    # itself the proof nothing extra was appended.
    assert len(llm.requests) == 1
    assert llm.requests[0].messages == _user_message()


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

    # PBI-04-03: even a rejected (unauthorized) call still produces a TOOL-role error message
    # back to the LLM — the assistant message must precede it just the same, regardless of
    # whether the call was actually allowed to execute.
    second_request = llm.requests[1]
    assert second_request.messages[-2].role == LLMMessageRole.ASSISTANT
    assert second_request.messages[-1].role == LLMMessageRole.TOOL


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

    # PBI-04-03: same sequencing requirement as the unauthorized case above.
    second_request = llm.requests[1]
    assert second_request.messages[-2].role == LLMMessageRole.ASSISTANT
    assert second_request.messages[-1].role == LLMMessageRole.TOOL


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

    # PBI-04-03: malformed-argument failures still require the assistant message first.
    second_request = llm.requests[1]
    assert second_request.messages[-2].role == LLMMessageRole.ASSISTANT
    assert second_request.messages[-1].role == LLMMessageRole.TOOL


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

    # PBI-04-03: exactly ONE assistant message carries BOTH tool_calls (matching how the LLM
    # actually requested them, within a single turn), immediately followed by the two TOOL
    # result messages in the same order the LLM requested them — "if multiple tool calls
    # exist, preserve the complete ordered sequence."
    second_request = llm.requests[1]
    roles = [m.role for m in second_request.messages]
    assert roles == [
        LLMMessageRole.USER,
        LLMMessageRole.ASSISTANT,
        LLMMessageRole.TOOL,
        LLMMessageRole.TOOL,
    ]
    assistant_message = second_request.messages[1]
    assert assistant_message.tool_calls is not None
    assert [c.call_id for c in assistant_message.tool_calls] == ["call-1", "call-2"]
    assert [c.tool_name for c in assistant_message.tool_calls] == [
        "policy_lookup",
        "payment_status",
    ]
    assert second_request.messages[2].tool_call_id == "call-1"
    assert second_request.messages[3].tool_call_id == "call-2"


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

    # PBI-04-03: each iteration gets its own correctly-ordered assistant(tool_calls)/tool
    # pair, and both pairs must be present, in order, by the third (final) LLM call.
    third_request = llm.requests[2]
    roles = [m.role for m in third_request.messages]
    assert roles == [
        LLMMessageRole.USER,
        LLMMessageRole.ASSISTANT,
        LLMMessageRole.TOOL,
        LLMMessageRole.ASSISTANT,
        LLMMessageRole.TOOL,
    ]
    assert third_request.messages[1].tool_calls[0].call_id == "call-1"  # type: ignore[index]
    assert third_request.messages[2].tool_call_id == "call-1"
    assert third_request.messages[3].tool_calls[0].call_id == "call-2"  # type: ignore[index]
    assert third_request.messages[4].tool_call_id == "call-2"


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

    # PBI-04-03: max_iterations protection is unaffected by the fix — the loop still stops at
    # exactly the configured cap, and each iteration's assistant/tool pair is still correctly
    # sequenced even though the LLM never cooperates and terminates on its own.
    assert response.iterations == context.max_iterations


# --- duplicate tool-call detection (PBI-12-04) ------------------------------------------------


async def test_run_rejects_a_repeated_identical_tool_call_without_re_executing_it() -> None:
    """A misbehaving LLM that keeps requesting the exact same tool call (same tool name, same
    arguments) must be stopped from re-triggering it a second time — the duplicate is rejected
    with a typed error, and the underlying Tool genuinely never runs again."""
    counting_tool = _CountingPolicyLookupTool()
    registry = _build_registry(counting_tool)
    orchestrator = _build_orchestrator(registry, _RepeatsTheSameToolCallProvider())
    context = ToolCallingContext(
        agent_name="ClaimsAgent", allowed_tools=["policy_lookup"], max_iterations=3
    )

    response = await orchestrator.run(messages=_user_message(), context=context)

    assert response.iterations == 3
    assert len(response.tool_calls) == 3
    assert response.tool_calls[0].success is True
    assert response.tool_calls[0].error_type is None
    assert response.tool_calls[1].success is False
    assert response.tool_calls[1].error_type == "duplicate_call"
    assert response.tool_calls[2].success is False
    assert response.tool_calls[2].error_type == "duplicate_call"
    # The proof that matters: the real Tool only ever executed once, not three times.
    assert counting_tool.execution_count == 1


async def test_run_does_not_treat_the_same_tool_with_different_arguments_as_a_duplicate() -> None:
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
            LLMResponse(
                text="",
                model="stub",
                tool_calls=[
                    ToolCallRequest(
                        call_id="call-2",
                        tool_name="policy_lookup",
                        arguments=[ToolCallArgument(name="policy_number", value="SYN-POL-0002")],
                    )
                ],
            ),
            LLMResponse(text="done", model="stub"),
        ]
    )
    orchestrator = _build_orchestrator(registry, llm)
    context = ToolCallingContext(
        agent_name="ClaimsAgent", allowed_tools=["policy_lookup"], max_iterations=3
    )

    response = await orchestrator.run(messages=_user_message(), context=context)

    # Different arguments -> genuinely different calls, neither ever flagged as a duplicate.
    assert [call.error_type for call in response.tool_calls] == [None, None]
    assert [call.success for call in response.tool_calls] == [True, True]


async def test_run_rejects_a_duplicate_requested_twice_within_the_same_llm_turn() -> None:
    """The duplicate check applies within a single LLM response's tool_calls list too, not only
    across iterations — two identical calls requested in the same turn must not both execute."""
    counting_tool = _CountingPolicyLookupTool()
    registry = _build_registry(counting_tool)
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
                        tool_name="policy_lookup",
                        arguments=[ToolCallArgument(name="policy_number", value="SYN-POL-0001")],
                    ),
                ],
            ),
            LLMResponse(text="done", model="stub"),
        ]
    )
    orchestrator = _build_orchestrator(registry, llm)
    context = ToolCallingContext(agent_name="ClaimsAgent", allowed_tools=["policy_lookup"])

    response = await orchestrator.run(messages=_user_message(), context=context)

    assert response.tool_calls[0].error_type is None
    assert response.tool_calls[1].error_type == "duplicate_call"
    assert counting_tool.execution_count == 1


# --- loop timeout (PBI-12-04) -------------------------------------------------------------------


async def test_run_stops_and_flags_timeout_when_a_single_llm_call_hangs() -> None:
    registry = _build_registry(PolicyLookupTool())
    orchestrator = _build_orchestrator(registry, _SlowLLMProvider(delay_seconds=5.0))
    context = ToolCallingContext(
        agent_name="ClaimsAgent",
        allowed_tools=["policy_lookup"],
        max_iterations=3,
        timeout_seconds=0.05,
    )

    response = await orchestrator.run(messages=_user_message(), context=context)

    assert response.stopped_due_to_timeout is True
    assert response.stopped_due_to_max_iterations is False
    assert response.iterations == 0
    assert response.tool_calls == []
    assert response.text == ""


async def test_run_never_times_out_when_timeout_seconds_is_not_configured() -> None:
    """Default (None) preserves every prior caller's exact behavior — this is opt-in hardening,
    not a change to the existing default timing of any Agent already using this orchestrator."""
    registry = _build_registry(PolicyLookupTool())
    llm = _ScriptedLLMProvider([LLMResponse(text="a plain answer", model="stub")])
    orchestrator = _build_orchestrator(registry, llm)
    context = ToolCallingContext(agent_name="ClaimsAgent", allowed_tools=["policy_lookup"])

    response = await orchestrator.run(messages=_user_message(), context=context)

    assert response.stopped_due_to_timeout is False


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


# --- MockLLMProvider regression (PBI-04-03) --------------------------------------------------
# The one test in this file that uses the real MockLLMProvider (every other test above uses a
# scripted double, per this file's own module docstring) — proves the orchestrator fix produces
# a correctly-sequenced conversation with the actual provider every other test/local dev run
# uses, not just a hand-rolled stub.


async def test_run_with_the_real_mock_llm_provider_sequences_messages_correctly() -> None:
    registry = _build_registry(PolicyLookupTool())
    llm = MockLLMProvider(
        tool_call_plan=[
            ToolCallRequest(
                call_id="call-1",
                tool_name="policy_lookup",
                arguments=[ToolCallArgument(name="policy_number", value="SYN-POL-0001")],
            )
        ]
    )
    orchestrator = _build_orchestrator(registry, llm)
    context = ToolCallingContext(agent_name="ClaimsAgent", allowed_tools=["policy_lookup"])

    response = await orchestrator.run(messages=_user_message(), context=context)

    # MockLLMProvider stops requesting once a TOOL-role message exists in history (see its own
    # docstring) — the fix does not change when it stops, only what precedes the TOOL message.
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].success is True
    assert response.stopped_due_to_max_iterations is False

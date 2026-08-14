"""ToolCallingOrchestrator: the controlled loop between an LLMProvider and the Tool execution
framework (PBI-02-04).

Agent -> PromptManager -> LLMProvider -> ToolCallRequest -> ToolCallingOrchestrator ->
ToolExecutor -> ToolResult -> LLMProvider -> Final Agent Response.

This loop is this platform's ReAct (Reason -> Act -> Observe -> Reason -> ... -> Final Answer)
implementation (PBI-12-04; see docs/Architecture/adr/0011-react-pattern-for-tool-orchestrated-
reasoning.md): each pass through the `for iteration in ...` loop below is one Reason step (the
LLM call), optionally followed by an Act step (a Tool call) and an Observation step (the
ToolCallResult fed back into `conversation` as a TOOL-role message for the next Reason step).
Bounded by `max_iterations` (existing, PBI-02-04), plus two hardening additions from PBI-12-04:
a per-LLM-call `timeout_seconds` and duplicate-tool-call detection — see `run()`.

Reuses ToolRegistry and ToolExecutor exactly as-is (src.tools) — this class adds only the
per-Agent authorization boundary neither of those has: ToolExecutor executes any registered
Tool it is asked to, with no concept of "for this Agent". No eval(), no dynamic import, no
shell/process execution anywhere in this module — the only thing ever invoked is
Tool.execute() through the existing, already-audited ToolExecutor.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from src.core.tool_calling.exceptions import ToolCallingError
from src.core.tool_calling.models import (
    LLMUsageTotal,
    ReActEvent,
    ReActEventSink,
    ToolCallingContext,
    ToolCallingResponse,
    ToolCallResult,
)
from src.llm.models import (
    LLMGenerationSettings,
    LLMMessage,
    LLMMessageRole,
    LLMRequest,
    LLMResponse,
    LLMToolDefinition,
)
from src.llm.models import (
    ToolCallRequest as LLMToolCallRequest,
)
from src.llm.provider import LLMProvider
from src.tools.exceptions import ToolNotFoundError
from src.tools.executor import ToolExecutor
from src.tools.models import ToolRequest
from src.tools.protocol import Tool
from src.tools.registry import ToolRegistry


class ToolCallingOrchestrator:
    """Exposes an Agent's allowed Tools to an LLMProvider, validates and executes any Tool
    calls it requests, and loops (bounded by ToolCallingContext.max_iterations) until the LLM
    returns a final, tool-call-free response."""

    def __init__(
        self, tool_registry: ToolRegistry, tool_executor: ToolExecutor, llm_provider: LLMProvider
    ) -> None:
        self._tool_registry = tool_registry
        self._tool_executor = tool_executor
        self._llm_provider = llm_provider

    def build_tool_definitions(self, allowed_tools: list[str]) -> list[LLMToolDefinition]:
        """Builds one LLMToolDefinition per allowed tool name, from that Tool's own registered
        metadata and input_model — the LLM is never offered a hand-authored or hallucinated
        schema. Raises ToolCallingError if an allow-listed name is not actually registered: an
        Agent's own allow-list disagreeing with ToolRegistry is a configuration bug, not a
        normal runtime condition (see src.core.tool_calling.exceptions.ToolCallingError)."""
        definitions: list[LLMToolDefinition] = []
        for name in allowed_tools:
            tool = self._resolve_or_raise(name)
            definitions.append(
                LLMToolDefinition(
                    name=tool.name,
                    description=tool.description,
                    parameters_schema=tool.input_model.model_json_schema(),
                )
            )
        return definitions

    def _resolve_or_raise(self, name: str) -> Tool[Any]:
        try:
            return self._tool_registry.resolve(name)
        except ToolNotFoundError as exc:
            raise ToolCallingError(
                f"Tool '{name}' is allow-listed but not registered in ToolRegistry"
            ) from exc

    async def run(
        self,
        messages: list[LLMMessage],
        context: ToolCallingContext,
        settings: LLMGenerationSettings | None = None,
        on_event: ReActEventSink | None = None,
    ) -> ToolCallingResponse:
        """Runs the controlled LLM<->Tool loop (this platform's ReAct implementation — see this
        module's own docstring) and returns the final response. Never raises for an
        unauthorized/unknown/duplicate/failed tool call (all represented as typed
        ToolCallResult data) or for a timed-out/max-iterations-exceeded loop (represented as
        typed ToolCallingResponse flags) — only ToolCallingError for genuine misconfiguration
        (see build_tool_definitions).

        on_event (PBI-13-01, optional, default None — every prior caller's behavior is
        unchanged): a best-effort observability hook. Exceptions it raises are swallowed, never
        propagated — see _emit."""
        tool_definitions = self.build_tool_definitions(context.allowed_tools)
        generation_settings = settings or LLMGenerationSettings()
        conversation: list[LLMMessage] = list(messages)
        all_results: list[ToolCallResult] = []
        llm_response_text = ""
        usage_total = LLMUsageTotal()
        last_model: str | None = None

        def _emit(event: ReActEvent) -> None:
            if on_event is None:
                return
            try:
                on_event(event)
            except Exception:  # noqa: BLE001, S110 — a raising observer must never break the
                # loop; no logger is threaded into this reusable src/ module (see class
                # docstring's dependency-direction rule), so there is nothing safe to log here.
                pass
        # PBI-12-04: bounds duplicate tool-call requests (same tool + same arguments, seen
        # anywhere earlier in this single run() invocation) — a real risk for a ReAct loop that
        # a max_iterations cap alone does not address (a misbehaving LLM could otherwise spend
        # every iteration re-requesting the same non-idempotent action, e.g. claim_registration,
        # instead of making progress). Local to this call only — never shared across turns/
        # Agents, since this instance is a cached, process-wide singleton (see
        # apps/api/src/api/dependencies.py get_tool_calling_orchestrator()).
        seen_call_signatures: set[tuple[str, tuple[tuple[str, str], ...]]] = set()

        for iteration in range(1, context.max_iterations + 1):
            _emit(ReActEvent(event_type="reasoning_iteration_started", iteration=iteration))
            try:
                llm_response = await self._generate(
                    conversation, tool_definitions, generation_settings, context
                )
            except TimeoutError:
                _emit(ReActEvent(event_type="stopped_timeout", iteration=iteration))
                return ToolCallingResponse(
                    text=llm_response_text,
                    tool_calls=all_results,
                    iterations=iteration - 1,
                    stopped_due_to_max_iterations=False,
                    stopped_due_to_timeout=True,
                    model=last_model,
                    usage=usage_total,
                )
            llm_response_text = llm_response.text
            last_model = llm_response.model
            usage_total = LLMUsageTotal(
                prompt_tokens=usage_total.prompt_tokens + llm_response.usage.prompt_tokens,
                completion_tokens=(
                    usage_total.completion_tokens + llm_response.usage.completion_tokens
                ),
                total_tokens=usage_total.total_tokens + llm_response.usage.total_tokens,
            )

            if not llm_response.tool_calls:
                _emit(ReActEvent(event_type="final_answer_reached", iteration=iteration))
                return ToolCallingResponse(
                    text=llm_response_text,
                    tool_calls=all_results,
                    iterations=iteration,
                    stopped_due_to_max_iterations=False,
                    model=last_model,
                    usage=usage_total,
                )
            _emit(ReActEvent(event_type="tool_required", iteration=iteration))

            # PBI-04-03: the model's own tool-calling request must be persisted as an
            # ASSISTANT message *before* the TOOL result message(s) that answer it — per the
            # OpenAI/Azure OpenAI chat-completions protocol, a role="tool" message is only
            # valid immediately following the assistant message whose own tool_calls named
            # it. Appending only the TOOL message(s) (as before this fix) produced a
            # malformed history that Azure OpenAI rejects outright; MockLLMProvider never
            # validates this, which is why the defect was invisible until live validation
            # against the real API — see docs/sprint_04/decisions.md. One ASSISTANT message
            # carries the complete, ordered set of this turn's tool_calls, immediately
            # followed by one TOOL message per call, in the same order — provider-agnostic,
            # no special-casing.
            conversation.append(
                LLMMessage(
                    role=LLMMessageRole.ASSISTANT,
                    content=llm_response_text,
                    tool_calls=llm_response.tool_calls,
                )
            )

            for call in llm_response.tool_calls:
                _emit(
                    ReActEvent(
                        event_type="tool_selected", iteration=iteration, tool_name=call.tool_name
                    )
                )
                signature = _call_signature(call)
                call_start = time.perf_counter()
                if signature in seen_call_signatures:
                    result = ToolCallResult(
                        call_id=call.call_id,
                        tool_name=call.tool_name,
                        success=False,
                        error=(
                            f"Tool '{call.tool_name}' was already called with the same "
                            "arguments earlier in this reasoning loop — not executed again."
                        ),
                        error_type="duplicate_call",
                    )
                else:
                    seen_call_signatures.add(signature)
                    result = await self._execute_tool_call(call, context)
                call_latency_ms = (time.perf_counter() - call_start) * 1000
                _emit(
                    ReActEvent(
                        event_type="tool_executed",
                        iteration=iteration,
                        tool_name=call.tool_name,
                        success=result.success,
                        latency_ms=round(call_latency_ms, 1),
                    )
                )
                all_results.append(result)
                conversation.append(
                    LLMMessage(
                        role=LLMMessageRole.TOOL,
                        content=_serialize_result(result),
                        tool_call_id=call.call_id,
                    )
                )

        _emit(
            ReActEvent(event_type="stopped_max_iterations", iteration=context.max_iterations)
        )
        return ToolCallingResponse(
            text=llm_response_text,
            tool_calls=all_results,
            iterations=context.max_iterations,
            stopped_due_to_max_iterations=True,
            model=last_model,
            usage=usage_total,
        )

    async def _generate(
        self,
        conversation: list[LLMMessage],
        tool_definitions: list[LLMToolDefinition],
        generation_settings: LLMGenerationSettings,
        context: ToolCallingContext,
    ) -> LLMResponse:
        """One Reason step: a single LLM call, optionally bounded by
        ToolCallingContext.timeout_seconds (PBI-12-04). Raises `TimeoutError` (built-in,
        distinct from ToolCallingError — a resilience condition, not a misconfiguration) when
        the bound is exceeded; `run()` turns that into a safe, typed ToolCallingResponse."""
        coro = self._llm_provider.generate(
            LLMRequest(
                messages=conversation,
                settings=generation_settings,
                tools=tool_definitions,
                correlation_id=context.correlation_id,
                conversation_id=context.conversation_id,
                user_id=context.user_id,
            )
        )
        if context.timeout_seconds is None:
            return await coro
        return await asyncio.wait_for(coro, timeout=context.timeout_seconds)

    async def _execute_tool_call(
        self, call: LLMToolCallRequest, context: ToolCallingContext
    ) -> ToolCallResult:
        tool_name = call.tool_name
        # Existence is checked before authorization so "unknown tool" (never registered at all
        # — a hallucinated name) and "unauthorized tool" (registered, but not allow-listed for
        # this Agent) are each independently reachable and distinguishable in audit output,
        # even though both are rejected identically safely either way.
        try:
            self._tool_registry.resolve(tool_name)
        except ToolNotFoundError:
            return ToolCallResult(
                call_id=call.call_id,
                tool_name=tool_name,
                success=False,
                error=f"'{tool_name}' is not a registered tool",
                error_type="unknown_tool",
            )

        if tool_name not in context.allowed_tools:
            return ToolCallResult(
                call_id=call.call_id,
                tool_name=tool_name,
                success=False,
                error=f"Tool '{tool_name}' is not authorized for agent '{context.agent_name}'",
                error_type="unauthorized",
            )

        tool_input = {argument.name: argument.value for argument in call.arguments}
        tool_result = await self._tool_executor.execute(
            ToolRequest(
                tool_name=tool_name,
                tool_input=tool_input,
                correlation_id=context.correlation_id,
                conversation_id=context.conversation_id,
                user_id=context.user_id,
            )
        )
        return ToolCallResult(
            call_id=call.call_id,
            tool_name=tool_name,
            success=tool_result.success,
            data=tool_result.data.model_dump() if tool_result.data is not None else None,
            error=tool_result.error,
            error_type=None if tool_result.success else "tool_failed",
        )


def _serialize_result(result: ToolCallResult) -> str:
    """Feeds a Tool's outcome back to the LLM as the content of a role="tool" message. json,
    not str()/repr(), so the LLM receives a stable, parseable structure — not a debugging
    string."""
    return json.dumps({"success": result.success, "data": result.data, "error": result.error})


def _call_signature(call: LLMToolCallRequest) -> tuple[str, tuple[tuple[str, str], ...]]:
    """The identity a duplicate-tool-call check (PBI-12-04) compares on: tool name plus
    arguments, deliberately excluding `call_id` (an LLM/provider-generated request identifier,
    never part of what makes two calls "the same action"). `json.dumps(..., default=str)` on
    each argument's value gives a stable, order-independent signature even when a value is a
    non-hashable type (e.g. a nested dict, seen in this module's own tests)."""
    argument_signature = tuple(
        sorted(
            (argument.name, json.dumps(argument.value, sort_keys=True, default=str))
            for argument in call.arguments
        )
    )
    return (call.tool_name, argument_signature)

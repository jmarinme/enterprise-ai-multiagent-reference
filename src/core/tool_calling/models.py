"""Typed models for the Tool Calling orchestration framework (PBI-02-04), built on top of the
LLM protocol contracts (src.llm.models.LLMToolDefinition/ToolCallRequest/ToolCallArgument) and
the Tool execution framework (src.tools.models.ToolRequest/ToolResult).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

# Conservative default (CLAUDE.md §9's "explicit resilience" principle): enough for a typical
# "look something up, then answer" round trip, low enough that a misbehaving LLM that always
# requests another tool call cannot turn one Agent turn into an unbounded loop.
DEFAULT_MAX_TOOL_CALL_ITERATIONS = 3


class _CamelModel(BaseModel):
    """ToolCallResult is nested inside the transport-layer API response (POST /chat) via
    AgentResponse.tool_calls -> ChatResponse.toolCalls, so — like src.rag.grounding_models —
    it serializes with camelCase field names on the wire, matching this API's existing
    convention."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


ToolCallErrorType = Literal["unauthorized", "unknown_tool", "tool_failed", "duplicate_call"]


class ToolCallResult(_CamelModel):
    """The typed, safe outcome of one Tool Calling request — whether it succeeded, was
    rejected before execution (unauthorized/unknown_tool), or failed during execution/
    validation (tool_failed, exactly ToolExecutor's own success=False case passed through).
    Never contains a stack trace or raw internal exception text."""

    call_id: str
    tool_name: str
    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    error_type: ToolCallErrorType | None = None


class ToolCallingContext(BaseModel):
    """Per-call configuration and correlation identifiers for one ToolCallingOrchestrator.run()
    invocation. allowed_tools is the authorization boundary (CLAUDE.md §2/§3): only tools named
    here may ever be executed for this call, regardless of what the LLM requests."""

    agent_name: str
    allowed_tools: list[str] = Field(default_factory=list)
    correlation_id: str | None = None
    conversation_id: str | None = None
    user_id: str | None = None
    max_iterations: int = Field(default=DEFAULT_MAX_TOOL_CALL_ITERATIONS, ge=1)
    # PBI-12-04 (ReAct generalization hardening): per-LLM-call wall-clock bound, in addition to
    # max_iterations above. None (default) preserves every existing caller's exact prior
    # behavior — this is opt-in, not a change to Claims' or any test's current timing.
    timeout_seconds: float | None = Field(default=None, gt=0)


class LLMUsageTotal(BaseModel):
    """Token usage accumulated across every LLM call this run() invocation made — the ReAct
    loop's own calls only (src.llm.models.LLMUsage per-call values summed), never a fabricated
    total (PBI-13-01 §7)."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ToolCallingResponse(BaseModel):
    """The orchestrator's final output: the LLM's last text response, plus every ToolCallResult
    produced across every iteration of the loop. Internal-only (an Agent unpacks this into its
    own typed AgentResponse fields) — same reasoning as src.rag.grounding_models.
    GroundedResponse."""

    text: str
    tool_calls: list[ToolCallResult] = Field(default_factory=list)
    iterations: int
    # True only if max_iterations was reached without the LLM returning a final, tool-call-free
    # response — the loop still stops safely and returns whatever text/tool_calls exist so far,
    # it never raises (CLAUDE.md §11: a safe, understandable response is always required).
    stopped_due_to_max_iterations: bool = False
    # PBI-12-04: True only if ToolCallingContext.timeout_seconds elapsed waiting on a single LLM
    # call — same safe-stop guarantee as stopped_due_to_max_iterations above, never a raise.
    stopped_due_to_timeout: bool = False
    # PBI-13-01: observability additions, both purely additive (default empty/None preserves
    # every existing caller's exact prior behavior). `model` is the last LLM call's deployment/
    # model name; `usage` sums every LLM call's token usage across the whole run() invocation.
    model: str | None = None
    usage: LLMUsageTotal = Field(default_factory=LLMUsageTotal)


ReActEventType = Literal[
    "reasoning_iteration_started",
    "tool_required",
    "tool_selected",
    "tool_executed",
    "final_answer_reached",
    "stopped_max_iterations",
    "stopped_timeout",
]


class ReActEvent(BaseModel):
    """One safe, structural lifecycle event from a run() invocation — execution metadata only
    (event type, iteration number, tool name, success, latency). NEVER carries LLM reasoning
    text, prompt content, or tool arguments/results (CLAUDE.md §10, PBI-13-01 §8) — there is no
    field here capable of holding any of that."""

    event_type: ReActEventType
    iteration: int
    tool_name: str | None = None
    success: bool | None = None
    latency_ms: float | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


ReActEventSink = Callable[[ReActEvent], None]
"""A synchronous, best-effort observer. run() calls it inline and swallows any exception it
raises (PBI-13-01 §3: telemetry must never affect business behavior) — never awaited, never
required to succeed."""

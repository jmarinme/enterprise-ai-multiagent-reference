"""Typed models for the Tool Calling orchestration framework (PBI-02-04), built on top of the
LLM protocol contracts (src.llm.models.LLMToolDefinition/ToolCallRequest/ToolCallArgument) and
the Tool execution framework (src.tools.models.ToolRequest/ToolResult).
"""

from __future__ import annotations

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

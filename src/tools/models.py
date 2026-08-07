"""Typed models for the Tool execution framework.

Agent -> ToolExecutor -> ToolRegistry -> Tool -> Typed Input Validation -> Execution ->
Typed ToolResult -> Agent.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

ToolOutputT = TypeVar("ToolOutputT", bound=BaseModel)


class ToolMetadata(BaseModel):
    """Lightweight catalog entry for a registered Tool, returned by ToolRegistry.list()."""

    name: str
    description: str
    version: str


class ToolExecutionContext(BaseModel):
    """Correlation/conversation/user identifiers propagated into Tool execution."""

    correlation_id: str | None = None
    conversation_id: str | None = None
    user_id: str | None = None


class ToolRequest(BaseModel):
    """A request to execute a named Tool.

    `tool_input` is intentionally `dict[str, Any]`: the caller (an Agent) cannot statically
    know which Tool's input schema applies until `tool_name` is resolved at runtime. This is
    the one deliberately untyped boundary in the framework — ToolExecutor validates it against
    the resolved Tool's own `input_model` before execution, and every stage downstream of that
    validation (including ToolResult.data) is fully typed.
    """

    tool_name: str
    tool_input: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None
    conversation_id: str | None = None
    user_id: str | None = None


# PEP 695 `class ToolResult[ToolOutputT](BaseModel):` syntax is Python 3.12-only and would be a
# SyntaxError under the 3.11.9 interpreter this project's local dev/test environment still runs
# (pre-existing gap, see docs/sprint_00/decisions.md R-01). Generic[T] subclassing remains fully
# correct on 3.12 too, so it stays until the environment is upgraded.
class ToolResult(BaseModel, Generic[ToolOutputT]):  # noqa: UP046
    """Typed outcome of a Tool execution. ToolExecutor always returns one of these — it never
    raises to the caller."""

    tool_name: str
    success: bool
    data: ToolOutputT | None = None
    error: str | None = None
    correlation_id: str | None = None

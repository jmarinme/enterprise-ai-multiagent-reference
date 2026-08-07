"""Typed exceptions for the Tool Calling orchestration framework.

Deliberately minimal: expected, per-call outcomes (a tool the LLM requested being unauthorized,
unknown, or failing execution/validation) are represented as typed data on ToolCallResult, not
raised — mirroring src.tools.executor.ToolExecutor's own "never raise to the caller" contract,
which ToolCallingOrchestrator sits directly on top of. ToolCallingError is reserved for genuine
misconfiguration (e.g. an Agent's own allow-list naming a Tool that ToolRegistry does not
actually have registered) — a programming error to catch during development, not a normal
runtime path a user's message could trigger.
"""

from __future__ import annotations


class ToolCallingError(Exception):
    """Raised only for Tool Calling misconfiguration — never for a normal unauthorized/unknown/
    failed tool call, which are all safely represented as ToolCallResult data instead."""

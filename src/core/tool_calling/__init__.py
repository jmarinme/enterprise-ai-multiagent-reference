"""Controlled LLM-driven Tool Calling (PBI-02-04).

Agent -> PromptManager -> LLMProvider -> ToolCallRequest -> ToolCallingOrchestrator ->
ToolExecutor -> ToolResult -> LLMProvider -> Final Agent Response.

ToolCallingOrchestrator reuses ToolRegistry and ToolExecutor (src.tools) unchanged — it never
recreates Tool resolution or execution logic, only adds the per-Agent authorization boundary
those two do not have: ToolExecutor will happily execute any registered Tool, so enforcing
"only this Agent's allow-listed Tools may be invoked" is this package's own responsibility,
checked before ToolExecutor is ever called.
"""

from __future__ import annotations

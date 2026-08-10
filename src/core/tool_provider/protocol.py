"""ToolProvider — the location-transparent seam between a domain Agent and wherever a Tool
actually executes (in-process Python, or an Azure Function over HTTP).

Agents must never know where a Tool runs (CLAUDE.md §4.2/§5; Architecture Review Finding A-03;
docs/Architecture/adr/0003-azure-functions-tool-and-workflow-layer.md). Every ToolProvider
implementation exposes the exact same shape src.tools.executor.ToolExecutor already had — a
ToolProvider is a structural drop-in replacement for a ToolExecutor from an Agent's point of
view (Protocols are structural, no inheritance required).
"""

from __future__ import annotations

from typing import Any, Protocol

from src.tools.models import ToolRequest, ToolResult


class ToolProvider(Protocol):
    """Contract every Tool execution backend implements. Never raises to its caller — every
    failure mode is normalized into ToolResult(success=False, error=...), matching
    ToolExecutor's own contract (src.tools.executor)."""

    async def execute(self, request: ToolRequest) -> ToolResult[Any]: ...

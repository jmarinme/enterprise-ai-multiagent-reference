"""ToolProvider framework (PBI-06-01): the location-transparent seam between a domain Agent and
wherever a Tool actually executes — in-process (src.tools.executor.ToolExecutor) or an Azure
Function over HTTP. Resolves Architecture Review Finding A-03 / ADR-0003.
"""

from __future__ import annotations

from src.core.tool_provider.protocol import ToolProvider

__all__ = ["ToolProvider"]

"""InProcessToolProvider — the default ToolProvider backend (TOOL_PROVIDER=inprocess). Tools
execute in the same Python process via the pre-existing ToolExecutor/ToolRegistry framework
(src.tools.*). Introduced by PBI-06-01 purely as a selection seam — it duplicates none of
ToolExecutor's logic, it delegates to it unchanged.
"""

from __future__ import annotations

from typing import Any

from src.tools.executor import ToolExecutor
from src.tools.models import ToolRequest, ToolResult


class InProcessToolProvider:
    """ToolProvider backend that delegates every call to an existing ToolExecutor instance."""

    def __init__(self, tool_executor: ToolExecutor) -> None:
        self._tool_executor = tool_executor

    async def execute(self, request: ToolRequest) -> ToolResult[Any]:
        return await self._tool_executor.execute(request)

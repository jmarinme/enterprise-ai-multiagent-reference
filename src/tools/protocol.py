"""Tool Protocol — the contract every deterministic capability implements.

Agents depend only on ToolExecutor (executor.py) and this Protocol — never on a concrete Tool
class or the integration it wraps (a database, a REST API, an Azure service).
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from src.tools.models import ToolExecutionContext, ToolResult

ToolInputT = TypeVar("ToolInputT", bound=BaseModel)


class Tool(Protocol[ToolInputT]):
    """Contract every Tool implements: a typed input contract in, a typed ToolResult out."""

    name: str
    description: str
    version: str
    input_model: type[ToolInputT]

    async def execute(
        self, tool_input: ToolInputT, context: ToolExecutionContext
    ) -> ToolResult[Any]: ...

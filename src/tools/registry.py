"""ToolRegistry: maps a tool name to a concrete Tool instance.

No hardcoded tool routing — every entry arrives via register(), mirroring
src.supervisor.registry.AgentRegistry. Unlike AgentRegistry, duplicate registration is a
programming error here (two Tools competing for the same name) and fails explicitly rather
than silently overwriting.
"""

from __future__ import annotations

from typing import Any, Protocol

from src.tools.exceptions import ToolAlreadyRegisteredError, ToolNotFoundError
from src.tools.models import ToolMetadata
from src.tools.protocol import Tool


class ToolRegistry(Protocol):
    """Contract for registering and resolving Tools by name."""

    def register(self, tool: Tool[Any]) -> None: ...

    def unregister(self, name: str) -> None: ...

    def resolve(self, name: str) -> Tool[Any]: ...

    def list(self) -> list[ToolMetadata]: ...


class InMemoryToolRegistry:
    """Dict-backed ToolRegistry. Holds no hardcoded knowledge of any specific tool."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool[Any]] = {}

    def register(self, tool: Tool[Any]) -> None:
        if tool.name in self._tools:
            raise ToolAlreadyRegisteredError(tool.name)
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def resolve(self, name: str) -> Tool[Any]:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolNotFoundError(name)
        return tool

    def list(self) -> list[ToolMetadata]:
        return [
            ToolMetadata(name=tool.name, description=tool.description, version=tool.version)
            for tool in self._tools.values()
        ]

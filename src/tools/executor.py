"""ToolExecutor: resolves a Tool from the ToolRegistry, validates typed input, executes it,
and normalizes every failure mode into a typed ToolResult. Contains no business logic —
every domain capability lives inside a concrete Tool, never here.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from src.tools.exceptions import ToolExecutionError, ToolNotFoundError, ToolValidationError
from src.tools.models import ToolExecutionContext, ToolRequest, ToolResult
from src.tools.protocol import Tool
from src.tools.registry import ToolRegistry


class ToolExecutor:
    """Executes a ToolRequest against the ToolRegistry. Always returns a ToolResult; never
    raises to the caller — every typed failure mode is caught and normalized here."""

    def __init__(self, tool_registry: ToolRegistry) -> None:
        self._tool_registry = tool_registry

    async def execute(self, request: ToolRequest) -> ToolResult[Any]:
        context = ToolExecutionContext(
            correlation_id=request.correlation_id,
            conversation_id=request.conversation_id,
            user_id=request.user_id,
        )

        try:
            tool = self._tool_registry.resolve(request.tool_name)
            validated_input = self._validate_input(tool, request.tool_input)
            return await self._invoke(tool, validated_input, context)
        except (ToolNotFoundError, ToolValidationError, ToolExecutionError) as exc:
            return ToolResult(
                tool_name=request.tool_name,
                success=False,
                error=str(exc),
                correlation_id=request.correlation_id,
            )

    def _validate_input(self, tool: Tool[Any], raw_input: dict[str, Any]) -> BaseModel:
        try:
            return tool.input_model.model_validate(raw_input)
        except ValidationError as exc:
            raise ToolValidationError(tool.name, str(exc)) from exc

    async def _invoke(
        self, tool: Tool[Any], validated_input: BaseModel, context: ToolExecutionContext
    ) -> ToolResult[Any]:
        try:
            return await tool.execute(validated_input, context)
        except Exception as exc:
            # Intentional broad catch: this is the framework boundary between arbitrary Tool
            # implementations and the typed ToolResult contract every caller relies on. Any
            # unexpected failure inside a Tool must never propagate as a raw exception.
            raise ToolExecutionError(tool.name, str(exc)) from exc

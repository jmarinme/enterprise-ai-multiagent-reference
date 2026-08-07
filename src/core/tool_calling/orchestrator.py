"""ToolCallingOrchestrator: the controlled loop between an LLMProvider and the Tool execution
framework (PBI-02-04).

Agent -> PromptManager -> LLMProvider -> ToolCallRequest -> ToolCallingOrchestrator ->
ToolExecutor -> ToolResult -> LLMProvider -> Final Agent Response.

Reuses ToolRegistry and ToolExecutor exactly as-is (src.tools) — this class adds only the
per-Agent authorization boundary neither of those has: ToolExecutor executes any registered
Tool it is asked to, with no concept of "for this Agent". No eval(), no dynamic import, no
shell/process execution anywhere in this module — the only thing ever invoked is
Tool.execute() through the existing, already-audited ToolExecutor.
"""

from __future__ import annotations

import json
from typing import Any

from src.core.tool_calling.exceptions import ToolCallingError
from src.core.tool_calling.models import ToolCallingContext, ToolCallingResponse, ToolCallResult
from src.llm.models import (
    LLMGenerationSettings,
    LLMMessage,
    LLMMessageRole,
    LLMRequest,
    LLMToolDefinition,
)
from src.llm.models import (
    ToolCallRequest as LLMToolCallRequest,
)
from src.llm.provider import LLMProvider
from src.tools.exceptions import ToolNotFoundError
from src.tools.executor import ToolExecutor
from src.tools.models import ToolRequest
from src.tools.protocol import Tool
from src.tools.registry import ToolRegistry


class ToolCallingOrchestrator:
    """Exposes an Agent's allowed Tools to an LLMProvider, validates and executes any Tool
    calls it requests, and loops (bounded by ToolCallingContext.max_iterations) until the LLM
    returns a final, tool-call-free response."""

    def __init__(
        self, tool_registry: ToolRegistry, tool_executor: ToolExecutor, llm_provider: LLMProvider
    ) -> None:
        self._tool_registry = tool_registry
        self._tool_executor = tool_executor
        self._llm_provider = llm_provider

    def build_tool_definitions(self, allowed_tools: list[str]) -> list[LLMToolDefinition]:
        """Builds one LLMToolDefinition per allowed tool name, from that Tool's own registered
        metadata and input_model — the LLM is never offered a hand-authored or hallucinated
        schema. Raises ToolCallingError if an allow-listed name is not actually registered: an
        Agent's own allow-list disagreeing with ToolRegistry is a configuration bug, not a
        normal runtime condition (see src.core.tool_calling.exceptions.ToolCallingError)."""
        definitions: list[LLMToolDefinition] = []
        for name in allowed_tools:
            tool = self._resolve_or_raise(name)
            definitions.append(
                LLMToolDefinition(
                    name=tool.name,
                    description=tool.description,
                    parameters_schema=tool.input_model.model_json_schema(),
                )
            )
        return definitions

    def _resolve_or_raise(self, name: str) -> Tool[Any]:
        try:
            return self._tool_registry.resolve(name)
        except ToolNotFoundError as exc:
            raise ToolCallingError(
                f"Tool '{name}' is allow-listed but not registered in ToolRegistry"
            ) from exc

    async def run(
        self,
        messages: list[LLMMessage],
        context: ToolCallingContext,
        settings: LLMGenerationSettings | None = None,
    ) -> ToolCallingResponse:
        """Runs the controlled LLM<->Tool loop and returns the final response. Never raises for
        an unauthorized/unknown/failed tool call (all represented as typed ToolCallResult data)
        — only ToolCallingError for genuine misconfiguration (see build_tool_definitions)."""
        tool_definitions = self.build_tool_definitions(context.allowed_tools)
        generation_settings = settings or LLMGenerationSettings()
        conversation: list[LLMMessage] = list(messages)
        all_results: list[ToolCallResult] = []
        llm_response_text = ""

        for iteration in range(1, context.max_iterations + 1):
            llm_response = await self._llm_provider.generate(
                LLMRequest(
                    messages=conversation,
                    settings=generation_settings,
                    tools=tool_definitions,
                    correlation_id=context.correlation_id,
                    conversation_id=context.conversation_id,
                    user_id=context.user_id,
                )
            )
            llm_response_text = llm_response.text

            if not llm_response.tool_calls:
                return ToolCallingResponse(
                    text=llm_response_text,
                    tool_calls=all_results,
                    iterations=iteration,
                    stopped_due_to_max_iterations=False,
                )

            for call in llm_response.tool_calls:
                result = await self._execute_tool_call(call, context)
                all_results.append(result)
                conversation.append(
                    LLMMessage(
                        role=LLMMessageRole.TOOL,
                        content=_serialize_result(result),
                        tool_call_id=call.call_id,
                    )
                )

        return ToolCallingResponse(
            text=llm_response_text,
            tool_calls=all_results,
            iterations=context.max_iterations,
            stopped_due_to_max_iterations=True,
        )

    async def _execute_tool_call(
        self, call: LLMToolCallRequest, context: ToolCallingContext
    ) -> ToolCallResult:
        tool_name = call.tool_name
        # Existence is checked before authorization so "unknown tool" (never registered at all
        # — a hallucinated name) and "unauthorized tool" (registered, but not allow-listed for
        # this Agent) are each independently reachable and distinguishable in audit output,
        # even though both are rejected identically safely either way.
        try:
            self._tool_registry.resolve(tool_name)
        except ToolNotFoundError:
            return ToolCallResult(
                call_id=call.call_id,
                tool_name=tool_name,
                success=False,
                error=f"'{tool_name}' is not a registered tool",
                error_type="unknown_tool",
            )

        if tool_name not in context.allowed_tools:
            return ToolCallResult(
                call_id=call.call_id,
                tool_name=tool_name,
                success=False,
                error=f"Tool '{tool_name}' is not authorized for agent '{context.agent_name}'",
                error_type="unauthorized",
            )

        tool_input = {argument.name: argument.value for argument in call.arguments}
        tool_result = await self._tool_executor.execute(
            ToolRequest(
                tool_name=tool_name,
                tool_input=tool_input,
                correlation_id=context.correlation_id,
                conversation_id=context.conversation_id,
                user_id=context.user_id,
            )
        )
        return ToolCallResult(
            call_id=call.call_id,
            tool_name=tool_name,
            success=tool_result.success,
            data=tool_result.data.model_dump() if tool_result.data is not None else None,
            error=tool_result.error,
            error_type=None if tool_result.success else "tool_failed",
        )


def _serialize_result(result: ToolCallResult) -> str:
    """Feeds a Tool's outcome back to the LLM as the content of a role="tool" message. json,
    not str()/repr(), so the LLM receives a stable, parseable structure — not a debugging
    string."""
    return json.dumps({"success": result.success, "data": result.data, "error": result.error})

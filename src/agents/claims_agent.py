"""Mock Claims Agent. Deterministic response only — validates the orchestration architecture.
No insurance logic, no Azure OpenAI, no RAG. Implements the Agent Protocol (src.supervisor.registry).

Also demonstrates ToolExecutor injection (PBI-01-02): this agent depends on ToolExecutor —
never on a concrete Tool, a database, or an integration — the same way a future real Claims
Agent would call ClaimsStatusTool without knowing how it is implemented. The tool lookup here
uses a fixed, synthetic claim number purely to prove the wiring; it is still not real business
logic (no branching on the tool's result beyond a single success/failure text template).
"""

from __future__ import annotations

from src.supervisor.models import AgentRequest, AgentResponse, ConversationContext, IntentCategory
from src.tools.executor import ToolExecutor
from src.tools.models import ToolRequest


class ClaimsAgent:
    """Deterministic mock agent registered for the CLAIMS intent."""

    name = "ClaimsAgent"

    def __init__(self, tool_executor: ToolExecutor) -> None:
        self._tool_executor = tool_executor

    async def handle(self, request: AgentRequest, context: ConversationContext) -> AgentResponse:
        tool_result = await self._tool_executor.execute(
            ToolRequest(
                tool_name="claims_status",
                tool_input={"claim_number": "CLM-SYN-0001"},
                correlation_id=request.correlation_id,
                conversation_id=context.conversation_id,
                user_id=request.user_id,
            )
        )

        if tool_result.success and tool_result.data is not None:
            tool_summary = f" (synthetic claim lookup: status={tool_result.data.status})"
        else:
            tool_summary = f" (synthetic claim lookup unavailable: {tool_result.error})"

        return AgentResponse(
            conversation_id=context.conversation_id,
            agent=self.name,
            intent=IntentCategory.CLAIMS,
            response=(
                "This is a mock Claims Agent response. Claims business logic is not "
                "implemented in this PBI." + tool_summary
            ),
        )

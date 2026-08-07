"""Mock Claims Agent. Deterministic response only — validates the orchestration architecture.
No insurance logic, no Azure OpenAI, no RAG. Implements the Agent Protocol (src.supervisor.registry).

Also demonstrates ToolExecutor injection (PBI-01-02) and PromptManager injection (PBI-01-03):
this agent depends on ToolExecutor and PromptManager — never on a concrete Tool, a concrete
PromptProvider, a database, or an integration — the same way a future real Claims Agent would
call ClaimsStatusTool and render "claims.system" without knowing how either is implemented.
No prompt text is embedded here: the actual wording lives only in
configs/prompts/claims/system.md.
"""

from __future__ import annotations

from src.prompts.manager import PromptManager
from src.prompts.models import PromptRenderContext
from src.supervisor.models import AgentRequest, AgentResponse, ConversationContext, IntentCategory
from src.tools.executor import ToolExecutor
from src.tools.models import ToolRequest


class ClaimsAgent:
    """Deterministic mock agent registered for the CLAIMS intent."""

    name = "ClaimsAgent"

    def __init__(self, tool_executor: ToolExecutor, prompt_manager: PromptManager) -> None:
        self._tool_executor = tool_executor
        self._prompt_manager = prompt_manager

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
            tool_summary = f"synthetic claim lookup: status={tool_result.data.status}"
        else:
            tool_summary = f"synthetic claim lookup unavailable: {tool_result.error}"

        rendered_prompt = await self._prompt_manager.render(
            "claims.system",
            PromptRenderContext(
                conversation_id=context.conversation_id,
                user_id=request.user_id,
                intent=IntentCategory.CLAIMS.value,
                conversation_summary=context.summary,
                tool_summaries=[tool_summary],
                agent_name=self.name,
            ),
        )

        return AgentResponse(
            conversation_id=context.conversation_id,
            agent=self.name,
            intent=IntentCategory.CLAIMS,
            response=(
                "This is a mock Claims Agent response. Claims business logic is not "
                f"implemented in this PBI. ({tool_summary}) "
                f"[prompt={rendered_prompt.identifier}@{rendered_prompt.metadata.version}]"
            ),
        )

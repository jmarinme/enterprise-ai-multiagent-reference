"""Mock Claims Agent. Deterministic response only — validates the orchestration architecture.
No insurance logic, no Azure OpenAI, no RAG. Implements the Agent Protocol (src.supervisor.registry).

Demonstrates ToolExecutor injection (PBI-01-02), PromptManager injection (PBI-01-03), and
LLMProvider injection (PBI-01-04): this agent depends on ToolExecutor, PromptManager, and
LLMProvider — never on a concrete Tool, PromptProvider, Azure OpenAI, the OpenAI SDK, a
database, or any other integration. The same way a future real Claims Agent would call
ClaimsStatusTool, render "claims.system", and call an LLM without knowing how any of the
three are implemented. Still no embedded prompt text and no embedded LLM configuration —
both come from PromptManager and the injected LLMGenerationSettings default.
"""

from __future__ import annotations

from src.llm.models import LLMGenerationSettings, LLMMessage, LLMMessageRole, LLMRequest
from src.llm.provider import LLMProvider
from src.prompts.manager import PromptManager
from src.prompts.models import PromptRenderContext
from src.supervisor.models import AgentRequest, AgentResponse, ConversationContext, IntentCategory
from src.tools.executor import ToolExecutor
from src.tools.models import ToolRequest


class ClaimsAgent:
    """Deterministic mock agent registered for the CLAIMS intent."""

    name = "ClaimsAgent"

    def __init__(
        self,
        tool_executor: ToolExecutor,
        prompt_manager: PromptManager,
        llm_provider: LLMProvider,
    ) -> None:
        self._tool_executor = tool_executor
        self._prompt_manager = prompt_manager
        self._llm_provider = llm_provider

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

        llm_response = await self._llm_provider.generate(
            LLMRequest(
                messages=[
                    LLMMessage(role=LLMMessageRole.SYSTEM, content=rendered_prompt.text),
                    LLMMessage(role=LLMMessageRole.USER, content=request.message),
                ],
                settings=LLMGenerationSettings(),
                correlation_id=request.correlation_id,
                conversation_id=context.conversation_id,
                user_id=request.user_id,
            )
        )

        return AgentResponse(
            conversation_id=context.conversation_id,
            agent=self.name,
            intent=IntentCategory.CLAIMS,
            response=(
                f"{llm_response.text} "
                f"[prompt={rendered_prompt.identifier}@{rendered_prompt.metadata.version}] "
                f"[{tool_summary}]"
            ),
        )

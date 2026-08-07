"""Commercial Intake Agent: a synthetic commercial/business lead-intake flow (PBI-01-07).

Implements the Agent Protocol (src.supervisor.registry). Guides a caller through reporting a
new commercial inquiry over multiple turns: collects the minimum lead information (company
name, contact name, preferred contact detail, insurance need, risk description) and registers
a synthetic lead. Per CLAUDE.md §2, this Agent must never quote, underwrite, define premiums,
or guarantee acceptance — it only gathers information and registers the inquiry.

Business facts and field extraction are fully deterministic (src.agents.commercial.extraction,
src.agents.commercial.workflow) for the same reason as ClaimsAgent (PBI-01-05) and BrokerAgent
(PBI-01-06): MockLLMProvider cannot perform real NLU. PromptManager and LLMProvider are still
genuinely invoked every turn (provable via the response's [prompt=...]/[llm=...] annotations,
rendered by the shared src.agents.shared.annotation helper), so the same Agent code works
unmodified once a real AzureOpenAIProvider is configured — but the LLM is never the source of
a business fact (CLAUDE.md §3).

This file intentionally duplicates ClaimsAgent's/BrokerAgent's business-flow shape (load state
-> run state machine -> annotate -> return) rather than sharing a base class with them — only
the two genuinely identical pieces (state persistence, prompt+LLM annotation) were extracted
into src.agents.shared once this, the third agent, needed them too; see
docs/sprint_01/decisions.md.
"""

from __future__ import annotations

from src.agents.commercial.state import CommercialIntakeState
from src.agents.commercial.workflow import advance_commercial_intake
from src.agents.shared.annotation import annotate_with_prompt_and_llm
from src.agents.shared.state_persistence import load_agent_state
from src.llm.provider import LLMProvider
from src.prompts.manager import PromptManager
from src.prompts.models import PromptRenderContext
from src.supervisor.models import AgentRequest, AgentResponse, ConversationContext, IntentCategory
from src.tools.executor import ToolExecutor

_STATE_METADATA_KEY = "commercialIntakeState"
_SAFE_FALLBACK_MESSAGE = (
    "We're sorry, something went wrong while processing your inquiry. Please try again, or "
    "contact support if the issue continues."
)
_NO_NOTICE_FALLBACK = "Thanks — please continue."


class CommercialIntakeAgent:
    """Deterministic, multi-turn commercial-intake agent registered for the COMMERCIAL intent."""

    name = "CommercialIntakeAgent"

    def __init__(
        self, tool_executor: ToolExecutor, prompt_manager: PromptManager, llm_provider: LLMProvider
    ) -> None:
        self._tool_executor = tool_executor
        self._prompt_manager = prompt_manager
        self._llm_provider = llm_provider

    async def handle(self, request: AgentRequest, context: ConversationContext) -> AgentResponse:
        state = load_agent_state(context.metadata, _STATE_METADATA_KEY, CommercialIntakeState)

        try:
            state, notices = await advance_commercial_intake(
                state=state,
                message=request.message,
                tool_executor=self._tool_executor,
                correlation_id=request.correlation_id,
                conversation_id=context.conversation_id,
                user_id=request.user_id,
            )
        except Exception:  # noqa: BLE001
            # Intentional broad catch, same boundary rationale as ClaimsAgent.handle() and
            # BrokerAgent.handle(): no stack trace or internal exception detail may ever reach
            # the user, and this is the outermost boundary (nothing wraps CommercialIntakeAgent).
            return AgentResponse(
                conversation_id=context.conversation_id,
                agent=self.name,
                intent=IntentCategory.COMMERCIAL,
                response=_SAFE_FALLBACK_MESSAGE,
                metadata={_STATE_METADATA_KEY: state.model_dump_json()},
            )

        response_text = " ".join(notices) if notices else _NO_NOTICE_FALLBACK
        response_text = await annotate_with_prompt_and_llm(
            response_text=response_text,
            prompt_identifier="commercial.system",
            prompt_manager=self._prompt_manager,
            llm_provider=self._llm_provider,
            render_context=PromptRenderContext(
                conversation_id=context.conversation_id,
                user_id=request.user_id,
                intent=IntentCategory.COMMERCIAL.value,
                conversation_summary=context.summary,
                tool_summaries=notices,
                agent_name=self.name,
            ),
            user_message=request.message,
            correlation_id=request.correlation_id,
            conversation_id=context.conversation_id,
            user_id=request.user_id,
        )

        return AgentResponse(
            conversation_id=context.conversation_id,
            agent=self.name,
            intent=IntentCategory.COMMERCIAL,
            response=response_text,
            metadata={_STATE_METADATA_KEY: state.model_dump_json()},
        )

"""Broker Services Agent: a synthetic broker-support flow (PBI-01-06).

Implements the Agent Protocol (src.supervisor.registry). Supports a broker asking about a
policy/transaction status, a policy's payment status, or their own commissions — including
registering a synthetic commission-payment request when eligible. Per CLAUDE.md §2, this Agent
must never execute payments, approve commissions, modify policies, or expose another broker's
information.

Business facts and field/inquiry-type extraction are fully deterministic
(src.agents.broker.extraction, src.agents.broker.workflow) for the same reason as ClaimsAgent
(PBI-01-05): MockLLMProvider cannot perform real NLU. PromptManager and LLMProvider are still
genuinely invoked every turn (provable via the response's [prompt=...]/[llm=...] annotations),
so the same Agent code works unmodified once a real AzureOpenAIProvider is configured — but the
LLM is never the source of a business fact (CLAUDE.md §3).

This file intentionally duplicates ClaimsAgent's shape (load state -> run state machine ->
annotate -> return) rather than sharing a base class with it — see
docs/sprint_01/decisions.md for why that extraction was deferred (only two data points so far).
"""

from __future__ import annotations

from pydantic import ValidationError

from src.agents.broker.state import BrokerInquiryState
from src.agents.broker.workflow import advance_broker_inquiry
from src.llm.exceptions import LLMError
from src.llm.models import LLMGenerationSettings, LLMMessage, LLMMessageRole, LLMRequest
from src.llm.provider import LLMProvider
from src.prompts.exceptions import PromptError
from src.prompts.manager import PromptManager
from src.prompts.models import PromptRenderContext
from src.supervisor.models import AgentRequest, AgentResponse, ConversationContext, IntentCategory
from src.tools.executor import ToolExecutor

_STATE_METADATA_KEY = "brokerInquiryState"
_SAFE_FALLBACK_MESSAGE = (
    "We're sorry, something went wrong while processing your broker request. Please try "
    "again, or contact support if the issue continues."
)
_NO_NOTICE_FALLBACK = "Thanks — please continue."


class BrokerAgent:
    """Deterministic, multi-turn broker-services agent registered for the BROKER intent."""

    name = "BrokerAgent"

    def __init__(
        self, tool_executor: ToolExecutor, prompt_manager: PromptManager, llm_provider: LLMProvider
    ) -> None:
        self._tool_executor = tool_executor
        self._prompt_manager = prompt_manager
        self._llm_provider = llm_provider

    async def handle(self, request: AgentRequest, context: ConversationContext) -> AgentResponse:
        state = _load_state(context.metadata)

        try:
            state, notices = await advance_broker_inquiry(
                state=state,
                message=request.message,
                tool_executor=self._tool_executor,
                correlation_id=request.correlation_id,
                conversation_id=context.conversation_id,
                user_id=request.user_id,
            )
        except Exception:  # noqa: BLE001
            # Intentional broad catch, same boundary rationale as ClaimsAgent.handle(): no
            # stack trace or internal exception detail may ever reach the user, and this is
            # the outermost boundary (nothing wraps BrokerAgent).
            return AgentResponse(
                conversation_id=context.conversation_id,
                agent=self.name,
                intent=IntentCategory.BROKER,
                response=_SAFE_FALLBACK_MESSAGE,
                metadata={_STATE_METADATA_KEY: state.model_dump_json()},
            )

        response_text = " ".join(notices) if notices else _NO_NOTICE_FALLBACK
        response_text = await self._annotate(response_text, request, context, notices)

        return AgentResponse(
            conversation_id=context.conversation_id,
            agent=self.name,
            intent=IntentCategory.BROKER,
            response=response_text,
            metadata={_STATE_METADATA_KEY: state.model_dump_json()},
        )

    async def _annotate(
        self,
        response_text: str,
        request: AgentRequest,
        context: ConversationContext,
        notices: list[str],
    ) -> str:
        """Invoke PromptManager + LLMProvider so both frameworks stay genuinely wired, and
        append a provable annotation of that invocation. Degrades gracefully (deterministic
        response_text alone) on any Prompt/LLM failure."""
        try:
            rendered_prompt = await self._prompt_manager.render(
                "broker.system",
                PromptRenderContext(
                    conversation_id=context.conversation_id,
                    user_id=request.user_id,
                    intent=IntentCategory.BROKER.value,
                    conversation_summary=context.summary,
                    tool_summaries=notices,
                    agent_name=self.name,
                ),
            )
        except PromptError:
            return response_text

        prompt_annotation = (
            f"[prompt={rendered_prompt.identifier}@{rendered_prompt.metadata.version}]"
        )

        try:
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
        except LLMError:
            return f"{response_text} {prompt_annotation}"

        return f"{response_text} {prompt_annotation} [llm={llm_response.model}]"


def _load_state(metadata: dict[str, str]) -> BrokerInquiryState:
    raw = metadata.get(_STATE_METADATA_KEY)
    if raw is None:
        return BrokerInquiryState()
    try:
        return BrokerInquiryState.model_validate_json(raw)
    except ValidationError:
        # A corrupt/incompatible stored snapshot must never crash the conversation — start a
        # fresh inquiry rather than surfacing a deserialization error to the user.
        return BrokerInquiryState()

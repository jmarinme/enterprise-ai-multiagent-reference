"""Claims Agent: a synthetic after-hours claim-notice intake flow (PBI-01-05).

Implements the Agent Protocol (src.supervisor.registry). Guides a caller through reporting a
claim over multiple turns: collects the minimum required information, validates the policy and
its payment status via approved Tools, registers a synthetic claim notice, and may assign a
synthetic adjuster. Per CLAUDE.md §2, this Agent must never determine final coverage, reject a
claim, or authorize indemnity — it only gathers and reports facts.

Business facts and field extraction are fully deterministic (src.agents.claims.extraction,
src.agents.claims.workflow) because MockLLMProvider is intentionally content-agnostic and
cannot perform real NLU. PromptManager and LLMProvider are still genuinely invoked every turn
(their identity is provable via the response's [prompt=...]/[llm=...] annotations) so the same
Agent code works unmodified once a real AzureOpenAIProvider is configured — but the LLM is
never the source of a business fact (CLAUDE.md §3).

Per-turn working state (which fields are still missing, validation results, claim reference,
etc.) is not core business truth — it is in-progress session notes, round-tripped through
AgentResponse.metadata / ConversationContext.metadata (see src.agents.claims.state for why this
does not violate CLAUDE.md §4.3).
"""

from __future__ import annotations

from pydantic import ValidationError

from src.agents.claims.state import ClaimsIntakeState
from src.agents.claims.workflow import advance_claims_intake
from src.llm.exceptions import LLMError
from src.llm.models import LLMGenerationSettings, LLMMessage, LLMMessageRole, LLMRequest
from src.llm.provider import LLMProvider
from src.prompts.exceptions import PromptError
from src.prompts.manager import PromptManager
from src.prompts.models import PromptRenderContext
from src.supervisor.models import AgentRequest, AgentResponse, ConversationContext, IntentCategory
from src.tools.executor import ToolExecutor

_STATE_METADATA_KEY = "claimsIntakeState"
_SAFE_FALLBACK_MESSAGE = (
    "We're sorry, something went wrong while processing your claim information. Please try "
    "again, or contact support if the issue continues."
)
_NO_NOTICE_FALLBACK = "Thanks — please continue."


class ClaimsAgent:
    """Deterministic, multi-turn claims-intake agent registered for the CLAIMS intent."""

    name = "ClaimsAgent"

    def __init__(
        self, tool_executor: ToolExecutor, prompt_manager: PromptManager, llm_provider: LLMProvider
    ) -> None:
        self._tool_executor = tool_executor
        self._prompt_manager = prompt_manager
        self._llm_provider = llm_provider

    async def handle(self, request: AgentRequest, context: ConversationContext) -> AgentResponse:
        state = _load_state(context.metadata)

        try:
            state, notices = await advance_claims_intake(
                state=state,
                message=request.message,
                tool_executor=self._tool_executor,
                correlation_id=request.correlation_id,
                conversation_id=context.conversation_id,
                user_id=request.user_id,
            )
        except Exception:  # noqa: BLE001
            # Intentional broad catch: this is the boundary between the claims-intake state
            # machine and the safe-response guarantee CLAUDE.md §11/PBI-01-05 require — no
            # stack trace or internal exception detail may ever reach the user. ToolExecutor
            # already normalizes every Tool failure into a ToolResult, so reaching this branch
            # means an unexpected bug, not an ordinary business-flow error. Unlike
            # ToolExecutor's own broad catch, this is the outermost boundary (nothing wraps
            # ClaimsAgent), so there is nothing further to re-raise to.
            return AgentResponse(
                conversation_id=context.conversation_id,
                agent=self.name,
                intent=IntentCategory.CLAIMS,
                response=_SAFE_FALLBACK_MESSAGE,
                metadata={_STATE_METADATA_KEY: state.model_dump_json()},
            )

        response_text = " ".join(notices) if notices else _NO_NOTICE_FALLBACK
        response_text = await self._annotate(response_text, request, context, notices)

        return AgentResponse(
            conversation_id=context.conversation_id,
            agent=self.name,
            intent=IntentCategory.CLAIMS,
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
        response_text alone) on any Prompt/LLM failure — CLAUDE.md §11 requires a safe,
        understandable response even when a downstream framework fails."""
        try:
            rendered_prompt = await self._prompt_manager.render(
                "claims.system",
                PromptRenderContext(
                    conversation_id=context.conversation_id,
                    user_id=request.user_id,
                    intent=IntentCategory.CLAIMS.value,
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


def _load_state(metadata: dict[str, str]) -> ClaimsIntakeState:
    raw = metadata.get(_STATE_METADATA_KEY)
    if raw is None:
        return ClaimsIntakeState()
    try:
        return ClaimsIntakeState.model_validate_json(raw)
    except ValidationError:
        # A corrupt/incompatible stored snapshot must never crash the conversation — start a
        # fresh intake rather than surfacing a deserialization error to the user.
        return ClaimsIntakeState()

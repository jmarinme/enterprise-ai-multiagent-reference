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

ToolCallingOrchestrator (PBI-12-04 — generalizes PBI-02-04's ClaimsAgent-only wiring to every
specialist agent; see docs/Architecture/adr/0011-react-pattern-for-tool-orchestrated-reasoning.md):
an additive, isolated ReAct (Reason -> Act -> Observe -> ... -> Final Answer) capability run
alongside — never in place of — advance_commercial_intake's own deterministic Tool calls,
exactly mirroring ClaimsAgent's/BrokerAgent's own _run_controlled_tool_calling. It proves the
LLM can request one of this Agent's allow-listed Tools
(src.core.tool_calling.policies.COMMERCIAL_ALLOWED_TOOLS) through the controlled, bounded
orchestration loop, with the outcome surfaced as typed AgentResponse.tool_calls. It never feeds
into CommercialIntakeState or the deterministic business-fact text, and a configuration failure
degrades gracefully exactly like a Prompt/LLM failure — it never blocks the turn.
"""

from __future__ import annotations

from src.agents.commercial.state import CommercialIntakeState
from src.agents.commercial.workflow import advance_commercial_intake
from src.agents.shared.language import LANGUAGE_METADATA_KEY, resolve_language
from src.agents.shared.memory import (
    GLOBAL_MEMORY_METADATA_KEY,
    ConversationMemory,
    load_memory,
    save_memory,
    update_memory,
)
from src.agents.shared.semantic_interpreter import interpret_semantics
from src.agents.shared.semantic_models import CommercialSemanticInterpretation
from src.agents.shared.state_persistence import carry_forward_other_agent_state, load_agent_state
from src.core.tool_calling.exceptions import ToolCallingError
from src.core.tool_calling.models import (
    DEFAULT_MAX_TOOL_CALL_ITERATIONS,
    ReActEventSink,
    ToolCallingContext,
    ToolCallingResponse,
)
from src.core.tool_calling.orchestrator import ToolCallingOrchestrator
from src.core.tool_calling.policies import COMMERCIAL_ALLOWED_TOOLS
from src.llm.models import LLMMessage, LLMMessageRole
from src.llm.provider import LLMProvider
from src.prompts.exceptions import PromptError
from src.prompts.manager import PromptManager
from src.prompts.models import PromptRenderContext
from src.supervisor.models import AgentRequest, AgentResponse, ConversationContext, IntentCategory
from src.tools.executor import ToolExecutor

_STATE_METADATA_KEY = "commercialIntakeState"
_SAFE_FALLBACK_MESSAGE = {
    "es-MX": (
        "Lo sentimos, algo salió mal al procesar tu solicitud. Intenta de nuevo, o contacta a "
        "soporte si el problema continúa."
    ),
    "en": (
        "We're sorry, something went wrong while processing your inquiry. Please try again, "
        "or contact support if the issue continues."
    ),
}
_NO_NOTICE_FALLBACK = {"es-MX": "Gracias — continuemos.", "en": "Thanks — please continue."}


def _prefill_from_memory(
    state: CommercialIntakeState, memory: ConversationMemory
) -> CommercialIntakeState:
    """Slot filling (PBI-09-01 requirement 2): reuse a business name or contact name already
    established in a different domain this same conversation. Applied every turn — unlike
    Claims/Broker, CommercialIntakeState has no field-clearing/decline transition anywhere in
    its workflow, so there is no stale-value risk in adopting a fact resolved elsewhere even
    after this Agent's own first turn (final validation: a caller who switches into Commercial
    mid-flow, before reaching company_name/contact_name, must still get the reuse benefit)."""
    updates: dict[str, str] = {}
    if state.company_name is None and memory.business_name:
        updates["company_name"] = memory.business_name
    if state.contact_name is None and memory.customer_name:
        updates["contact_name"] = memory.customer_name
    return state.model_copy(update=updates) if updates else state


class CommercialIntakeAgent:
    """Deterministic, multi-turn commercial-intake agent registered for the COMMERCIAL intent."""

    name = "CommercialIntakeAgent"

    def __init__(
        self,
        tool_executor: ToolExecutor,
        prompt_manager: PromptManager,
        llm_provider: LLMProvider,
        tool_calling_orchestrator: ToolCallingOrchestrator,
        tool_calling_max_iterations: int = DEFAULT_MAX_TOOL_CALL_ITERATIONS,
    ) -> None:
        self._tool_executor = tool_executor
        self._prompt_manager = prompt_manager
        self._llm_provider = llm_provider
        self._tool_calling_orchestrator = tool_calling_orchestrator
        self._tool_calling_max_iterations = tool_calling_max_iterations

    async def handle(
        self,
        request: AgentRequest,
        context: ConversationContext,
        on_react_event: ReActEventSink | None = None,
    ) -> AgentResponse:
        state = load_agent_state(context.metadata, _STATE_METADATA_KEY, CommercialIntakeState)
        # PBI-09-01 final validation: see claims_agent.py's identical rationale — a domain
        # re-entry message must never be blindly attributed to a stale last-asked question.
        if context.current_agent is not None and context.current_agent != self.name:
            state = state.model_copy(update={"last_asked_field": None})
        language = resolve_language(context.metadata, request.message)
        # PBI-05-01: preserve any other Agent's in-progress state across a cross-domain handoff.
        other_agent_state = carry_forward_other_agent_state(context.metadata, _STATE_METADATA_KEY)
        # PBI-09-01: global cross-agent memory — see claims_agent.py's identical rationale.
        # Applied every turn (see _prefill_from_memory's own docstring for why that is safe).
        memory = load_memory(context.metadata)
        state = _prefill_from_memory(state, memory)

        # PBI-14-03: the ONE shared semantic interpretation call (repurposes what was previously
        # annotate_with_prompt_and_llm's discarded-output call — LLM calls per turn are
        # unchanged) runs before the deterministic state machine so its structured entities/
        # confirmation can inform this turn's extraction and confirmation handling.
        semantic, diagnostics = await interpret_semantics(
            schema_name="commercial_semantic_interpretation",
            schema_type=CommercialSemanticInterpretation,
            prompt_identifier="commercial.system",
            prompt_manager=self._prompt_manager,
            llm_provider=self._llm_provider,
            render_context=PromptRenderContext(
                conversation_id=context.conversation_id,
                user_id=request.user_id,
                intent=IntentCategory.COMMERCIAL.value,
                conversation_summary=context.summary,
                agent_name=self.name,
            ),
            user_message=request.message,
            correlation_id=request.correlation_id,
            conversation_id=context.conversation_id,
            user_id=request.user_id,
        )

        try:
            state, notices = await advance_commercial_intake(
                state=state,
                message=request.message,
                tool_executor=self._tool_executor,
                language=language,
                correlation_id=request.correlation_id,
                conversation_id=context.conversation_id,
                user_id=request.user_id,
                semantic=semantic,
            )
        except Exception:  # noqa: BLE001
            # Intentional broad catch, same boundary rationale as ClaimsAgent.handle() and
            # BrokerAgent.handle(): no stack trace or internal exception detail may ever reach
            # the user, and this is the outermost boundary (nothing wraps CommercialIntakeAgent).
            return AgentResponse(
                conversation_id=context.conversation_id,
                agent=self.name,
                intent=IntentCategory.COMMERCIAL,
                response=_SAFE_FALLBACK_MESSAGE[language],
                metadata={
                    **other_agent_state,
                    _STATE_METADATA_KEY: state.model_dump_json(),
                    LANGUAGE_METADATA_KEY: language,
                    GLOBAL_MEMORY_METADATA_KEY: save_memory(memory),
                },
            )

        # PBI-09-01: feed every fact this turn actually learned/confirmed back into memory.
        reference_numbers = list(memory.reference_numbers)
        if state.lead_reference and state.lead_reference not in reference_numbers:
            reference_numbers.append(state.lead_reference)
        memory = update_memory(
            memory,
            agent_name=self.name,
            business_name=state.company_name,
            customer_name=state.contact_name,
            reference_numbers=reference_numbers,
        )

        response_text = " ".join(notices) if notices else _NO_NOTICE_FALLBACK[language]
        # PBI-04-04: diagnostic is metadata-only (technical detail end users must never see).
        # PBI-14-03: this diagnostic now comes from the semantic-interpretation call above.

        tool_calling_response = await self._run_controlled_tool_calling(
            request, context, on_react_event
        )

        return AgentResponse(
            conversation_id=context.conversation_id,
            agent=self.name,
            intent=IntentCategory.COMMERCIAL,
            response=response_text,
            metadata={
                **other_agent_state,
                _STATE_METADATA_KEY: state.model_dump_json(),
                LANGUAGE_METADATA_KEY: language,
                GLOBAL_MEMORY_METADATA_KEY: save_memory(memory),
                "diagnostics": diagnostics,
            },
            tool_calls=tool_calling_response.tool_calls,
            model=tool_calling_response.model,
            token_usage=tool_calling_response.usage,
        )

    async def _run_controlled_tool_calling(
        self,
        request: AgentRequest,
        context: ConversationContext,
        on_react_event: ReActEventSink | None = None,
    ) -> ToolCallingResponse:
        """Additive, isolated ReAct proof that the LLM can request one of this Agent's
        allow-listed Tools through ToolCallingOrchestrator (PBI-12-04, generalizing PBI-02-04's
        ClaimsAgent-only wiring) — entirely independent of, and never altering,
        advance_commercial_intake's own deterministic Tool calls above. Degrades to an empty
        ToolCallingResponse on PromptError/ToolCallingError, the same graceful-degradation
        pattern ClaimsAgent._run_controlled_tool_calling uses."""
        try:
            rendered_prompt = await self._prompt_manager.render(
                "commercial.system",
                PromptRenderContext(
                    conversation_id=context.conversation_id,
                    user_id=request.user_id,
                    intent=IntentCategory.COMMERCIAL.value,
                    conversation_summary=context.summary,
                    agent_name=self.name,
                ),
            )
        except PromptError:
            return ToolCallingResponse(text="", iterations=0)

        try:
            return await self._tool_calling_orchestrator.run(
                messages=[
                    LLMMessage(role=LLMMessageRole.SYSTEM, content=rendered_prompt.text),
                    LLMMessage(role=LLMMessageRole.USER, content=request.message),
                ],
                context=ToolCallingContext(
                    agent_name=self.name,
                    allowed_tools=list(COMMERCIAL_ALLOWED_TOOLS),
                    correlation_id=request.correlation_id,
                    conversation_id=context.conversation_id,
                    user_id=request.user_id,
                    max_iterations=self._tool_calling_max_iterations,
                ),
                on_event=on_react_event,
            )
        except ToolCallingError:
            return ToolCallingResponse(text="", iterations=0)
        except Exception:  # noqa: BLE001
            # PBI-12-04 hardening (discovered while generalizing this path to a second/third
            # Agent): ToolCallingOrchestrator.run() does not itself catch a genuine LLMProvider
            # failure (e.g. a sustained outage after AzureOpenAIProvider's own retry/circuit-
            # breaker layer is exhausted) — only ToolCallingError (misconfiguration) is handled
            # above. Since this whole method is an additive, isolated capability that must never
            # block the turn (see this method's own docstring), any other exception here is
            # degraded exactly the same way, not allowed to propagate past this boundary.
            return ToolCallingResponse(text="", iterations=0)

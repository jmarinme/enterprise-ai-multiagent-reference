"""Broker Services Agent: a synthetic broker-support flow (PBI-01-06).

Implements the Agent Protocol (src.supervisor.registry). Supports a broker asking about a
policy/transaction status, a policy's payment status, or their own commissions — including
registering a synthetic commission-payment request when eligible. Per CLAUDE.md §2, this Agent
must never execute payments, approve commissions, modify policies, or expose another broker's
information.

Business facts and field/inquiry-type extraction are fully deterministic
(src.agents.broker.extraction, src.agents.broker.workflow) for the same reason as ClaimsAgent
(PBI-01-05): MockLLMProvider cannot perform real NLU. PromptManager and LLMProvider are still
genuinely invoked every turn (provable via the response's [prompt=...]/[llm=...] annotations,
rendered by the shared src.agents.shared.annotation helper), so the same Agent code works
unmodified once a real AzureOpenAIProvider is configured — but the LLM is never the source of
a business fact (CLAUDE.md §3).

This file intentionally duplicates ClaimsAgent's business-flow shape (load state -> run state
machine -> annotate -> return) rather than sharing a base class with it — only the two
genuinely identical pieces (state persistence, prompt+LLM annotation) were extracted into
src.agents.shared once a third agent (Commercial Intake, PBI-01-07) needed them too; see
docs/sprint_01/decisions.md.

ToolCallingOrchestrator (PBI-12-04 — generalizes PBI-02-04's ClaimsAgent-only wiring to every
specialist agent; see docs/Architecture/adr/0011-react-pattern-for-tool-orchestrated-reasoning.md):
an additive, isolated ReAct (Reason -> Act -> Observe -> ... -> Final Answer) capability run
alongside — never in place of — advance_broker_inquiry's own deterministic Tool calls, exactly
mirroring ClaimsAgent's own _run_controlled_tool_calling. It proves the LLM can request one of
this Agent's allow-listed Tools (src.core.tool_calling.policies.BROKER_ALLOWED_TOOLS) through
the controlled, bounded orchestration loop, with the outcome surfaced as typed
AgentResponse.tool_calls. It never feeds into BrokerInquiryState or the deterministic
business-fact text, and a configuration failure degrades gracefully exactly like a Prompt/LLM
failure — it never blocks the turn.
"""

from __future__ import annotations

from src.agents.broker.state import BrokerInquiryState, BrokerInquiryStatus
from src.agents.broker.workflow import advance_broker_inquiry
from src.agents.shared.language import LANGUAGE_METADATA_KEY, resolve_language
from src.agents.shared.memory import (
    GLOBAL_MEMORY_METADATA_KEY,
    ConversationMemory,
    load_memory,
    save_memory,
    update_memory,
)
from src.agents.shared.semantic_interpreter import interpret_semantics
from src.agents.shared.semantic_models import (
    BrokerSemanticInterpretation,
    TurnInterpretation,
    to_domain_interpretation,
)
from src.agents.shared.state_persistence import carry_forward_other_agent_state, load_agent_state
from src.core.tool_calling.exceptions import ToolCallingError
from src.core.tool_calling.models import (
    DEFAULT_MAX_TOOL_CALL_ITERATIONS,
    ReActEventSink,
    ToolCallingContext,
    ToolCallingResponse,
)
from src.core.tool_calling.orchestrator import ToolCallingOrchestrator
from src.core.tool_calling.policies import BROKER_ALLOWED_TOOLS
from src.llm.models import LLMMessage, LLMMessageRole
from src.llm.provider import LLMProvider
from src.prompts.exceptions import PromptError
from src.prompts.manager import PromptManager
from src.prompts.models import PromptRenderContext
from src.supervisor.models import AgentRequest, AgentResponse, ConversationContext, IntentCategory
from src.tools.executor import ToolExecutor

_STATE_METADATA_KEY = "brokerInquiryState"
_SAFE_FALLBACK_MESSAGE = {
    "es-MX": (
        "Lo sentimos, algo salió mal al procesar tu solicitud de corredor. Intenta de nuevo, o "
        "contacta a soporte si el problema continúa."
    ),
    "en": (
        "We're sorry, something went wrong while processing your broker request. Please try "
        "again, or contact support if the issue continues."
    ),
}
_NO_NOTICE_FALLBACK = {"es-MX": "Gracias — continuemos.", "en": "Thanks — please continue."}


def _prefill_from_memory(state: BrokerInquiryState, memory: ConversationMemory) -> BrokerInquiryState:
    """Slot filling + entity-resolution reuse (PBI-09-01 requirements 2/3/10): if a broker was
    already identified (by resolved id) or a policy already validated in a different domain this
    same conversation, adopt it instead of asking again — pre-filling broker_id directly also
    lets _handle_collecting_information skip LOOKING_UP_BROKER entirely (state.
    missing_required_fields only requires broker_name when broker_id is still unset), avoiding a
    redundant broker_lookup Tool call (requirement 10).

    Applied every turn (not just this Agent's first) for broker_id/policy_number — neither is
    ever cleared by any Broker transition, so there is no stale-value risk, and a caller who
    switches into Broker mid-conversation (after this Agent's own first turn already ran) still
    benefits from a fact resolved afterward in another domain (final validation — PBI-09-01
    initially over-restricted this to first-turn-only, which missed exactly that case).
    broker_name is the one exception: _handle_looking_up_broker's not-found path clears it back
    to None so the caller can retry with a different name, so it is only ever adopted from
    memory on this Agent's genuine first turn — otherwise a failed-lookup retry could be
    silently overwritten by an older, unrelated, already-resolved name still sitting in memory."""
    updates: dict[str, str] = {}
    if state.broker_id is None and memory.broker_id:
        updates["broker_id"] = memory.broker_id
    if state.broker_name is None and memory.broker_name and state.status == BrokerInquiryStatus.NEW:
        updates["broker_name"] = memory.broker_name
    if state.policy_number is None and memory.policy_number:
        updates["policy_number"] = memory.policy_number
    return state.model_copy(update=updates) if updates else state


class BrokerAgent:
    """Deterministic, multi-turn broker-services agent registered for the BROKER intent."""

    name = "BrokerAgent"

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
        turn_interpretation: TurnInterpretation | None = None,
        turn_interpretation_diagnostic: str = "",
    ) -> AgentResponse:
        state = load_agent_state(context.metadata, _STATE_METADATA_KEY, BrokerInquiryState)
        # PBI-09-01 final validation: see claims_agent.py's identical rationale — a domain
        # re-entry message must never be blindly attributed to a stale last-asked question.
        if context.current_agent is not None and context.current_agent != self.name:
            state = state.model_copy(update={"last_asked_field": None})
        language = resolve_language(context.metadata, request.message)
        # PBI-05-01: preserve any other Agent's in-progress state across a cross-domain handoff.
        other_agent_state = carry_forward_other_agent_state(context.metadata, _STATE_METADATA_KEY)
        # PBI-09-01: global cross-agent memory — see claims_agent.py's identical rationale.
        # Applied every turn, not just the first (see _prefill_from_memory's own docstring for
        # why that is safe here).
        memory = load_memory(context.metadata)
        state = _prefill_from_memory(state, memory)

        # PBI-14-04: the Supervisor now performs the ONE shared semantic interpretation call
        # BEFORE routing (src.supervisor.semantic_routing) and hands the result to whichever
        # Agent it selects — reused here, never re-requested for the same turn. Falls back to
        # calling interpret_semantics itself only when turn_interpretation is None (no
        # Supervisor in front, e.g. a direct unit test) — the exact PBI-14-03 behavior,
        # preserved as a backward-compatible resilience path, not a normal-path second call.
        if turn_interpretation is not None:
            semantic = to_domain_interpretation(turn_interpretation, BrokerSemanticInterpretation)
            diagnostics = turn_interpretation_diagnostic
        else:
            semantic, diagnostics = await interpret_semantics(
                schema_name="broker_semantic_interpretation",
                schema_type=BrokerSemanticInterpretation,
                prompt_identifier="broker.system",
                prompt_manager=self._prompt_manager,
                llm_provider=self._llm_provider,
                render_context=PromptRenderContext(
                    conversation_id=context.conversation_id,
                    user_id=request.user_id,
                    intent=IntentCategory.BROKER.value,
                    conversation_summary=context.summary,
                    agent_name=self.name,
                ),
                user_message=request.message,
                correlation_id=request.correlation_id,
                conversation_id=context.conversation_id,
                user_id=request.user_id,
            )

        try:
            state, notices = await advance_broker_inquiry(
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
            # Intentional broad catch, same boundary rationale as ClaimsAgent.handle(): no
            # stack trace or internal exception detail may ever reach the user, and this is
            # the outermost boundary (nothing wraps BrokerAgent).
            return AgentResponse(
                conversation_id=context.conversation_id,
                agent=self.name,
                intent=IntentCategory.BROKER,
                response=_SAFE_FALLBACK_MESSAGE[language],
                metadata={
                    **other_agent_state,
                    _STATE_METADATA_KEY: state.model_dump_json(),
                    LANGUAGE_METADATA_KEY: language,
                    GLOBAL_MEMORY_METADATA_KEY: save_memory(memory),
                },
            )

        # PBI-09-01: feed every fact this turn actually learned/confirmed back into memory.
        # reference_numbers is append-only (computed here, not left to update_memory's plain
        # overlay) so an earlier turn's reference is never dropped by a later, unrelated one.
        reference_numbers = list(memory.reference_numbers)
        if (
            state.payment_request_reference
            and state.payment_request_reference not in reference_numbers
        ):
            reference_numbers.append(state.payment_request_reference)
        memory = update_memory(
            memory,
            agent_name=self.name,
            broker_id=state.broker_id,
            broker_name=state.broker_name,
            policy_number=state.policy_number,
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
            intent=IntentCategory.BROKER,
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
        advance_broker_inquiry's own deterministic Tool calls above. Degrades to an empty
        ToolCallingResponse on PromptError/ToolCallingError, the same graceful-degradation
        pattern ClaimsAgent._run_controlled_tool_calling uses."""
        try:
            rendered_prompt = await self._prompt_manager.render(
                "broker.system",
                PromptRenderContext(
                    conversation_id=context.conversation_id,
                    user_id=request.user_id,
                    intent=IntentCategory.BROKER.value,
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
                    allowed_tools=list(BROKER_ALLOWED_TOOLS),
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

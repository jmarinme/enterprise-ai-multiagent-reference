"""Claims Agent: a synthetic after-hours claim-notice intake flow (PBI-01-05, RAG-enabled by
PBI-02-01, grounded with typed citations by PBI-02-03, controlled Tool Calling by PBI-02-04).

Implements the Agent Protocol (src.supervisor.registry). Guides a caller through reporting a
claim over multiple turns: collects the minimum required information, validates the policy and
its payment status via approved Tools, registers a synthetic claim notice, and may assign a
synthetic adjuster. Per CLAUDE.md §2, this Agent must never determine final coverage, reject a
claim, or authorize indemnity — it only gathers and reports facts.

Business facts and field extraction are fully deterministic (src.agents.claims.extraction,
src.agents.claims.workflow) because MockLLMProvider is intentionally content-agnostic and
cannot perform real NLU. PromptManager and LLMProvider are still genuinely invoked every turn
(their identity is provable via AgentResponse.metadata["diagnostics"]'s [prompt=...]/[llm=...]
string, rendered by the shared src.agents.shared.annotation helper — metadata-only since
PBI-04-04, never shown to the end user) so the same Agent code works unmodified once a real
AzureOpenAIProvider is configured — but the LLM is never the source of a business fact
(CLAUDE.md §3).

Response text is deterministic and bilingual (PBI-04-04): src.agents.shared.language resolves
and "sticks" a per-conversation es-MX/en language, and every user-facing notice in
src.agents.claims.workflow is chosen from a bilingual catalog via src.agents.shared.messages.t
— never machine-translated or LLM-authored.

Per-turn working state (which fields are still missing, validation results, claim reference,
etc.) is not core business truth — it is in-progress session notes, round-tripped through
AgentResponse.metadata / ConversationContext.metadata via the shared
src.agents.shared.state_persistence helper (see src.agents.claims.state for why this does not
violate CLAUDE.md §4.3).

KnowledgeRetriever (PBI-02-01) supplies documentary reference material only — general claims
procedure/FAQ context for the LLM's prompt, never a business fact. It never touches
ClaimsIntakeState and is never treated as a source for policy/payment/claim status, which
always come from Tools (CLAUDE.md §4.4). Retrieval failure degrades gracefully, same as a
Prompt/LLM failure — it never blocks the deterministic business flow.

Grounder (PBI-02-03) turns retrieved chunks into a deterministic, deduplicated, top-k
GroundedContext before they reach the prompt, and produces the typed Citations/
GroundingMetadata carried on AgentResponse — replacing the earlier ad-hoc
"[knowledge=<source_id>,...]" text annotation with a proper typed contract. The LLM never
determines which citations appear; they are exactly what the Grounder made available.

ToolCallingOrchestrator (PBI-02-04) is an additive, isolated capability run alongside — never
in place of — advance_claims_intake's own deterministic Tool calls: it proves the LLM can
request one of this Agent's allow-listed Tools (src.core.tool_calling.policies.
CLAIMS_ALLOWED_TOOLS) through the controlled orchestration loop, with the outcome surfaced as
typed AgentResponse.tool_calls. It never feeds into ClaimsIntakeState or the deterministic
business-fact text, and a configuration failure degrades gracefully exactly like a Knowledge/
Prompt/LLM failure — it never blocks the turn.
"""

from __future__ import annotations

from src.agents.claims.state import ClaimsIntakeState
from src.agents.claims.workflow import advance_claims_intake
from src.agents.shared.annotation import annotate_with_prompt_and_llm
from src.agents.shared.language import LANGUAGE_METADATA_KEY, resolve_language
from src.agents.shared.state_persistence import load_agent_state
from src.core.tool_calling.exceptions import ToolCallingError
from src.core.tool_calling.models import (
    DEFAULT_MAX_TOOL_CALL_ITERATIONS,
    ToolCallingContext,
    ToolCallingResponse,
)
from src.core.tool_calling.orchestrator import ToolCallingOrchestrator
from src.core.tool_calling.policies import CLAIMS_ALLOWED_TOOLS
from src.llm.models import LLMMessage, LLMMessageRole
from src.llm.provider import LLMProvider
from src.prompts.exceptions import PromptError
from src.prompts.manager import PromptManager
from src.prompts.models import PromptRenderContext
from src.rag.exceptions import KnowledgeError
from src.rag.grounder import Grounder
from src.rag.models import KnowledgeChunk, KnowledgeQuery
from src.rag.retriever import KnowledgeRetriever
from src.supervisor.models import AgentRequest, AgentResponse, ConversationContext, IntentCategory
from src.tools.executor import ToolExecutor

_STATE_METADATA_KEY = "claimsIntakeState"
_SAFE_FALLBACK_MESSAGE = {
    "es-MX": (
        "Lo sentimos, algo salió mal al procesar tu información de siniestro. Intenta de "
        "nuevo, o contacta a soporte si el problema continúa."
    ),
    "en": (
        "We're sorry, something went wrong while processing your claim information. Please "
        "try again, or contact support if the issue continues."
    ),
}
_NO_NOTICE_FALLBACK = {"es-MX": "Gracias — continuemos.", "en": "Thanks — please continue."}
_KNOWLEDGE_TOP_K = 2
_CITATION_TOP_K = 2


class ClaimsAgent:
    """Deterministic, multi-turn claims-intake agent registered for the CLAIMS intent."""

    name = "ClaimsAgent"

    def __init__(
        self,
        tool_executor: ToolExecutor,
        prompt_manager: PromptManager,
        llm_provider: LLMProvider,
        knowledge_retriever: KnowledgeRetriever,
        grounder: Grounder,
        tool_calling_orchestrator: ToolCallingOrchestrator,
        tool_calling_max_iterations: int = DEFAULT_MAX_TOOL_CALL_ITERATIONS,
    ) -> None:
        self._tool_executor = tool_executor
        self._prompt_manager = prompt_manager
        self._llm_provider = llm_provider
        self._knowledge_retriever = knowledge_retriever
        self._grounder = grounder
        self._tool_calling_orchestrator = tool_calling_orchestrator
        self._tool_calling_max_iterations = tool_calling_max_iterations

    async def handle(self, request: AgentRequest, context: ConversationContext) -> AgentResponse:
        state = load_agent_state(context.metadata, _STATE_METADATA_KEY, ClaimsIntakeState)
        language = resolve_language(context.metadata, request.message)

        try:
            state, notices = await advance_claims_intake(
                state=state,
                message=request.message,
                tool_executor=self._tool_executor,
                language=language,
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
                response=_SAFE_FALLBACK_MESSAGE[language],
                metadata={
                    _STATE_METADATA_KEY: state.model_dump_json(),
                    LANGUAGE_METADATA_KEY: language,
                },
            )

        knowledge_chunks = await self._retrieve_knowledge(request.message)
        grounded_context = self._grounder.ground(knowledge_chunks, top_k=_CITATION_TOP_K)

        response_text = " ".join(notices) if notices else _NO_NOTICE_FALLBACK[language]
        # PBI-04-04: the [prompt=...]/[llm=...] diagnostic is metadata-only now (technical
        # detail end users must never see) — response_text itself is untouched by it.
        diagnostics = await annotate_with_prompt_and_llm(
            prompt_identifier="claims.system",
            prompt_manager=self._prompt_manager,
            llm_provider=self._llm_provider,
            render_context=PromptRenderContext(
                conversation_id=context.conversation_id,
                user_id=request.user_id,
                intent=IntentCategory.CLAIMS.value,
                conversation_summary=context.summary,
                tool_summaries=notices,
                agent_name=self.name,
                retrieved_knowledge=(
                    [grounded_context.context_text] if grounded_context.context_text else []
                ),
            ),
            user_message=request.message,
            correlation_id=request.correlation_id,
            conversation_id=context.conversation_id,
            user_id=request.user_id,
        )
        grounded_response = self._grounder.build_response(response_text, grounded_context)

        tool_calling_response = await self._run_controlled_tool_calling(request, context)

        return AgentResponse(
            conversation_id=context.conversation_id,
            agent=self.name,
            intent=IntentCategory.CLAIMS,
            response=grounded_response.text,
            metadata={
                _STATE_METADATA_KEY: state.model_dump_json(),
                LANGUAGE_METADATA_KEY: language,
                "diagnostics": diagnostics,
            },
            citations=grounded_response.citations,
            grounding_metadata=grounded_context.metadata,
            tool_calls=tool_calling_response.tool_calls,
        )

    async def _retrieve_knowledge(self, message: str) -> list[KnowledgeChunk]:
        """Best-effort documentary context for the prompt — never blocks or alters the
        deterministic business flow if retrieval fails."""
        try:
            result = await self._knowledge_retriever.retrieve(
                KnowledgeQuery(text=message, top_k=_KNOWLEDGE_TOP_K)
            )
        except KnowledgeError:
            return []
        return result.chunks

    async def _run_controlled_tool_calling(
        self, request: AgentRequest, context: ConversationContext
    ) -> ToolCallingResponse:
        """Additive, isolated proof that the LLM can request one of this Agent's allow-listed
        Tools through ToolCallingOrchestrator (PBI-02-04) — entirely independent of, and never
        altering, advance_claims_intake's own deterministic Tool calls above. Degrades to an
        empty ToolCallingResponse on PromptError/ToolCallingError, the same graceful-degradation
        pattern _retrieve_knowledge already uses for KnowledgeError."""
        try:
            rendered_prompt = await self._prompt_manager.render(
                "claims.system",
                PromptRenderContext(
                    conversation_id=context.conversation_id,
                    user_id=request.user_id,
                    intent=IntentCategory.CLAIMS.value,
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
                    allowed_tools=list(CLAIMS_ALLOWED_TOOLS),
                    correlation_id=request.correlation_id,
                    conversation_id=context.conversation_id,
                    user_id=request.user_id,
                    max_iterations=self._tool_calling_max_iterations,
                ),
            )
        except ToolCallingError:
            return ToolCallingResponse(text="", iterations=0)

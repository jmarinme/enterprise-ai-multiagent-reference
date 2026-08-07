"""Claims Agent: a synthetic after-hours claim-notice intake flow (PBI-01-05, RAG-enabled by
PBI-02-01, grounded with typed citations by PBI-02-03).

Implements the Agent Protocol (src.supervisor.registry). Guides a caller through reporting a
claim over multiple turns: collects the minimum required information, validates the policy and
its payment status via approved Tools, registers a synthetic claim notice, and may assign a
synthetic adjuster. Per CLAUDE.md §2, this Agent must never determine final coverage, reject a
claim, or authorize indemnity — it only gathers and reports facts.

Business facts and field extraction are fully deterministic (src.agents.claims.extraction,
src.agents.claims.workflow) because MockLLMProvider is intentionally content-agnostic and
cannot perform real NLU. PromptManager and LLMProvider are still genuinely invoked every turn
(their identity is provable via the response's [prompt=...]/[llm=...] annotations, rendered by
the shared src.agents.shared.annotation helper) so the same Agent code works unmodified once a
real AzureOpenAIProvider is configured — but the LLM is never the source of a business fact
(CLAUDE.md §3).

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
"""

from __future__ import annotations

from src.agents.claims.state import ClaimsIntakeState
from src.agents.claims.workflow import advance_claims_intake
from src.agents.shared.annotation import annotate_with_prompt_and_llm
from src.agents.shared.state_persistence import load_agent_state
from src.llm.provider import LLMProvider
from src.prompts.manager import PromptManager
from src.prompts.models import PromptRenderContext
from src.rag.exceptions import KnowledgeError
from src.rag.grounder import Grounder
from src.rag.models import KnowledgeChunk, KnowledgeQuery
from src.rag.retriever import KnowledgeRetriever
from src.supervisor.models import AgentRequest, AgentResponse, ConversationContext, IntentCategory
from src.tools.executor import ToolExecutor

_STATE_METADATA_KEY = "claimsIntakeState"
_SAFE_FALLBACK_MESSAGE = (
    "We're sorry, something went wrong while processing your claim information. Please try "
    "again, or contact support if the issue continues."
)
_NO_NOTICE_FALLBACK = "Thanks — please continue."
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
    ) -> None:
        self._tool_executor = tool_executor
        self._prompt_manager = prompt_manager
        self._llm_provider = llm_provider
        self._knowledge_retriever = knowledge_retriever
        self._grounder = grounder

    async def handle(self, request: AgentRequest, context: ConversationContext) -> AgentResponse:
        state = load_agent_state(context.metadata, _STATE_METADATA_KEY, ClaimsIntakeState)

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

        knowledge_chunks = await self._retrieve_knowledge(request.message)
        grounded_context = self._grounder.ground(knowledge_chunks, top_k=_CITATION_TOP_K)

        response_text = " ".join(notices) if notices else _NO_NOTICE_FALLBACK
        response_text = await annotate_with_prompt_and_llm(
            response_text=response_text,
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

        return AgentResponse(
            conversation_id=context.conversation_id,
            agent=self.name,
            intent=IntentCategory.CLAIMS,
            response=grounded_response.text,
            metadata={_STATE_METADATA_KEY: state.model_dump_json()},
            citations=grounded_response.citations,
            grounding_metadata=grounded_context.metadata,
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

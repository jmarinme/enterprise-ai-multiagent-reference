"""Unit tests specifically for ClaimsAgent's LLMProvider injection (PBI-01-04, evolved by
PBI-01-05): the agent depends on LLMProvider (never a concrete provider), and it is genuinely
invoked every turn — proven via the response's [llm=...] annotation. As of PBI-01-05, the
user-facing business-fact text is fully deterministic (derived from Tool/state-machine
results, never LLM wording), because MockLLMProvider is intentionally content-agnostic and
cannot produce meaningful, on-topic phrasing for a "concise, professional" claims
conversation — the LLM is never the source of a business fact (CLAUDE.md §3).
"""

from pathlib import Path

from src.agents.claims_agent import ClaimsAgent
from src.core.tool_calling.orchestrator import ToolCallingOrchestrator
from src.llm.mock_provider import MockLLMProvider
from src.prompts.filesystem_provider import FileSystemPromptProvider
from src.prompts.manager import PromptManager
from src.rag.grounder import Grounder
from src.rag.local_provider import LocalKnowledgeProvider
from src.rag.retriever import KnowledgeRetriever
from src.services.tools.policy_lookup_tool import PolicyLookupTool
from src.supervisor.models import AgentRequest, ConversationContext
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry


def _build_agent() -> ClaimsAgent:
    tool_registry = InMemoryToolRegistry()
    tool_registry.register(PolicyLookupTool())
    prompt_manager = PromptManager(
        provider=FileSystemPromptProvider(prompts_root=Path("configs/prompts"))
    )
    knowledge_retriever = KnowledgeRetriever(
        provider=LocalKnowledgeProvider(documents_root=Path("configs/knowledge_base"))
    )
    tool_executor = ToolExecutor(tool_registry=tool_registry)
    # PBI-14-03: ClaimsAgent's one per-turn LLM call now requests structured output
    # (src.agents.shared.semantic_interpreter) — a scripted plan is required for MockLLMProvider
    # to return a real completion (proving invocation) instead of degrading to a prompt-only
    # diagnostic, exactly like a real deployment would need a genuinely working model.
    llm_provider = MockLLMProvider(
        structured_response_plan={
            "claims_semantic_interpretation": '{"intent": "claims", "intent_confidence": 0.9}'
        }
    )
    return ClaimsAgent(
        tool_executor=tool_executor,
        prompt_manager=prompt_manager,
        llm_provider=llm_provider,
        knowledge_retriever=knowledge_retriever,
        grounder=Grounder(),
        tool_calling_orchestrator=ToolCallingOrchestrator(
            tool_registry=tool_registry, tool_executor=tool_executor, llm_provider=llm_provider
        ),
    )


async def test_claims_agent_response_proves_the_mock_llm_provider_was_invoked() -> None:
    agent = _build_agent()
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    response = await agent.handle(
        AgentRequest(message="I need to file a claim", user_id="user-1"), context
    )

    assert "[llm=mock-llm]" in response.metadata["diagnostics"]


async def test_claims_agent_response_is_fully_deterministic_for_the_same_state_and_message() -> (
    None
):
    agent = _build_agent()
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    first = await agent.handle(
        AgentRequest(message="I need to file a claim", user_id="user-1"), context
    )
    second = await agent.handle(
        AgentRequest(message="I need to file a claim", user_id="user-1"), context
    )

    assert first.response == second.response

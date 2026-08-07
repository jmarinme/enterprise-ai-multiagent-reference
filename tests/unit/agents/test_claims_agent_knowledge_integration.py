"""Unit tests specifically for ClaimsAgent's KnowledgeRetriever/Grounder injection (PBI-02-01,
grounded with typed citations by PBI-02-03): the agent depends on KnowledgeRetriever, never a
concrete KnowledgeProvider, retrieved knowledge never alters the deterministic business-fact
text, and retrieval failure degrades gracefully. Citations are asserted via the typed
AgentResponse.citations/grounding_metadata fields, not text annotations.
"""

from pathlib import Path

from src.agents.claims_agent import ClaimsAgent
from src.core.tool_calling.orchestrator import ToolCallingOrchestrator
from src.llm.mock_provider import MockLLMProvider
from src.prompts.filesystem_provider import FileSystemPromptProvider
from src.prompts.manager import PromptManager
from src.rag.exceptions import KnowledgeProviderError
from src.rag.grounder import Grounder
from src.rag.local_provider import LocalKnowledgeProvider
from src.rag.models import KnowledgeQuery, KnowledgeResult
from src.rag.retriever import KnowledgeRetriever
from src.services.tools.policy_lookup_tool import PolicyLookupTool
from src.supervisor.models import AgentRequest, ConversationContext
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry, ToolRegistry


class _RaisingKnowledgeProvider:
    async def retrieve(self, query: KnowledgeQuery) -> KnowledgeResult:
        raise KnowledgeProviderError("stub", "simulated outage")


class _EmptyKnowledgeProvider:
    async def retrieve(self, query: KnowledgeQuery) -> KnowledgeResult:
        return KnowledgeResult(query=query)


def _build_prompt_manager() -> PromptManager:
    return PromptManager(provider=FileSystemPromptProvider(prompts_root=Path("configs/prompts")))


def _build_tool_registry() -> ToolRegistry:
    registry = InMemoryToolRegistry()
    registry.register(PolicyLookupTool())
    return registry


def _build_agent(knowledge_retriever: KnowledgeRetriever) -> ClaimsAgent:
    tool_registry = _build_tool_registry()
    tool_executor = ToolExecutor(tool_registry=tool_registry)
    llm_provider = MockLLMProvider()
    return ClaimsAgent(
        tool_executor=tool_executor,
        prompt_manager=_build_prompt_manager(),
        llm_provider=llm_provider,
        knowledge_retriever=knowledge_retriever,
        grounder=Grounder(),
        tool_calling_orchestrator=ToolCallingOrchestrator(
            tool_registry=tool_registry, tool_executor=tool_executor, llm_provider=llm_provider
        ),
    )


async def test_response_includes_typed_citations_for_a_relevant_message() -> None:
    retriever = KnowledgeRetriever(
        provider=LocalKnowledgeProvider(documents_root=Path("configs/knowledge_base"))
    )
    agent = _build_agent(retriever)
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    response = await agent.handle(
        AgentRequest(message="I need to report a claim after hours", user_id="user-1"), context
    )

    assert len(response.citations) > 0
    assert response.citations[0].document_id.startswith("KB-CLAIMS-")
    assert response.grounding_metadata is not None
    assert response.grounding_metadata.is_grounded is True


async def test_response_has_no_citations_when_nothing_matches() -> None:
    retriever = KnowledgeRetriever(provider=_EmptyKnowledgeProvider())
    agent = _build_agent(retriever)
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    response = await agent.handle(
        AgentRequest(message="I need to report a claim after hours", user_id="user-1"), context
    )

    assert response.citations == []
    assert response.grounding_metadata is not None
    assert response.grounding_metadata.is_grounded is False


async def test_agent_degrades_gracefully_when_the_knowledge_retriever_fails() -> None:
    retriever = KnowledgeRetriever(provider=_RaisingKnowledgeProvider())
    agent = _build_agent(retriever)
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    response = await agent.handle(
        AgentRequest(message="I need to report a claim after hours", user_id="user-1"), context
    )

    assert "Could you provide your policy number?" in response.response
    assert response.citations == []
    assert "traceback" not in response.response.lower()
    assert "exception" not in response.response.lower()


async def test_retrieved_knowledge_never_changes_the_deterministic_business_fact_text() -> None:
    """The business-fact portion of the response (before the [prompt=...]/[llm=...]
    annotations) must be byte-identical whether or not knowledge was retrieved — knowledge is
    documentary context for the LLM only, never a business fact (CLAUDE.md §4.4). Citations are
    carried on a separate typed field, not inline in the response text, so this comparison
    still isolates the business-fact text correctly."""
    message = "I need to report a claim after hours"

    with_knowledge = await _build_agent(
        KnowledgeRetriever(provider=LocalKnowledgeProvider(documents_root=Path("configs/knowledge_base")))
    ).handle(
        AgentRequest(message=message, user_id="user-1"),
        ConversationContext(conversation_id="conv-1", user_id="user-1"),
    )
    without_knowledge = await _build_agent(KnowledgeRetriever(provider=_EmptyKnowledgeProvider())).handle(
        AgentRequest(message=message, user_id="user-1"),
        ConversationContext(conversation_id="conv-1", user_id="user-1"),
    )

    business_fact_text_with = with_knowledge.response.split(" [prompt=")[0]
    business_fact_text_without = without_knowledge.response.split(" [prompt=")[0]
    assert business_fact_text_with == business_fact_text_without

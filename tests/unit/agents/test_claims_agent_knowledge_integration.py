"""Unit tests specifically for ClaimsAgent's KnowledgeRetriever injection (PBI-02-01): the
agent depends on KnowledgeRetriever, never a concrete KnowledgeProvider, retrieved knowledge
never alters the deterministic business-fact text, and retrieval failure degrades gracefully.
"""

from pathlib import Path

from src.agents.claims_agent import ClaimsAgent
from src.llm.mock_provider import MockLLMProvider
from src.prompts.filesystem_provider import FileSystemPromptProvider
from src.prompts.manager import PromptManager
from src.rag.exceptions import KnowledgeProviderError
from src.rag.local_provider import LocalKnowledgeProvider
from src.rag.models import KnowledgeQuery, KnowledgeResult
from src.rag.retriever import KnowledgeRetriever
from src.services.tools.policy_lookup_tool import PolicyLookupTool
from src.supervisor.models import AgentRequest, ConversationContext
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry


class _RaisingKnowledgeProvider:
    async def retrieve(self, query: KnowledgeQuery) -> KnowledgeResult:
        raise KnowledgeProviderError("stub", "simulated outage")


class _EmptyKnowledgeProvider:
    async def retrieve(self, query: KnowledgeQuery) -> KnowledgeResult:
        return KnowledgeResult(query=query)


def _build_prompt_manager() -> PromptManager:
    return PromptManager(provider=FileSystemPromptProvider(prompts_root=Path("configs/prompts")))


def _build_tool_executor() -> ToolExecutor:
    registry = InMemoryToolRegistry()
    registry.register(PolicyLookupTool())
    return ToolExecutor(tool_registry=registry)


def _build_agent(knowledge_retriever: KnowledgeRetriever) -> ClaimsAgent:
    return ClaimsAgent(
        tool_executor=_build_tool_executor(),
        prompt_manager=_build_prompt_manager(),
        llm_provider=MockLLMProvider(),
        knowledge_retriever=knowledge_retriever,
    )


async def test_response_includes_a_knowledge_annotation_for_a_relevant_message() -> None:
    retriever = KnowledgeRetriever(
        provider=LocalKnowledgeProvider(documents_root=Path("configs/knowledge_base"))
    )
    agent = _build_agent(retriever)
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    response = await agent.handle(
        AgentRequest(message="I need to report a claim after hours", user_id="user-1"), context
    )

    assert "[knowledge=KB-CLAIMS-" in response.response


async def test_response_omits_the_knowledge_annotation_when_nothing_matches() -> None:
    retriever = KnowledgeRetriever(provider=_EmptyKnowledgeProvider())
    agent = _build_agent(retriever)
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    response = await agent.handle(
        AgentRequest(message="I need to report a claim after hours", user_id="user-1"), context
    )

    assert "[knowledge=" not in response.response


async def test_agent_degrades_gracefully_when_the_knowledge_retriever_fails() -> None:
    retriever = KnowledgeRetriever(provider=_RaisingKnowledgeProvider())
    agent = _build_agent(retriever)
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    response = await agent.handle(
        AgentRequest(message="I need to report a claim after hours", user_id="user-1"), context
    )

    assert "Could you provide your policy number?" in response.response
    assert "[knowledge=" not in response.response
    assert "traceback" not in response.response.lower()
    assert "exception" not in response.response.lower()


async def test_retrieved_knowledge_never_changes_the_deterministic_business_fact_text() -> None:
    """The business-fact portion of the response (before the [prompt=...]/[llm=...]/
    [knowledge=...] annotations) must be byte-identical whether or not knowledge was
    retrieved — knowledge is documentary context for the LLM only, never a business fact
    (CLAUDE.md §4.4)."""
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

"""Unit tests specifically for ClaimsAgent's ToolExecutor injection (PBI-01-02, evolved by
PBI-01-05): the agent depends on ToolExecutor, never a concrete Tool, and degrades gracefully
when a Tool is unavailable — proven by seeding a fully-collected claims-intake state directly
into ConversationContext.metadata (so the turn goes straight to policy validation) and
observing PolicyLookupTool's real, injected result in the response.
"""

from pathlib import Path

from src.agents.claims.state import ClaimsIntakeState, ClaimsIntakeStatus
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


def _build_prompt_manager() -> PromptManager:
    return PromptManager(provider=FileSystemPromptProvider(prompts_root=Path("configs/prompts")))


def _build_knowledge_retriever() -> KnowledgeRetriever:
    return KnowledgeRetriever(
        provider=LocalKnowledgeProvider(documents_root=Path("configs/knowledge_base"))
    )


def _ready_for_validation_state() -> ClaimsIntakeState:
    return ClaimsIntakeState(
        status=ClaimsIntakeStatus.VALIDATING_POLICY,
        policy_number="SYN-POL-0001",
        event_date="2026-08-01",
        event_location="Main St",
        loss_type="collision",
        loss_description="Rear-ended at a stoplight.",
        contact_name="Jane Caller",
        contact_phone="555-123-4567",
        injuries_reported=False,
        third_parties_involved=True,
    )


def _seed_context(state: ClaimsIntakeState) -> ConversationContext:
    return ConversationContext(
        conversation_id="conv-1",
        user_id="user-1",
        metadata={"claimsIntakeState": state.model_dump_json()},
    )


async def test_claims_agent_reports_the_real_policy_lookup_result_via_the_injected_tool_executor() -> (
    None
):
    registry = InMemoryToolRegistry()
    registry.register(PolicyLookupTool())
    tool_executor = ToolExecutor(tool_registry=registry)
    llm_provider = MockLLMProvider()
    agent = ClaimsAgent(
        tool_executor=tool_executor,
        prompt_manager=_build_prompt_manager(),
        llm_provider=llm_provider,
        knowledge_retriever=_build_knowledge_retriever(),
        grounder=Grounder(),
        tool_calling_orchestrator=ToolCallingOrchestrator(
            tool_registry=registry, tool_executor=tool_executor, llm_provider=llm_provider
        ),
    )
    context = _seed_context(_ready_for_validation_state())

    response = await agent.handle(AgentRequest(message="here you go", user_id="user-1"), context)

    assert "policy is active" in response.response.lower()


async def test_claims_agent_degrades_gracefully_when_policy_lookup_tool_is_not_registered() -> None:
    empty_registry = InMemoryToolRegistry()
    tool_executor = ToolExecutor(tool_registry=empty_registry)
    llm_provider = MockLLMProvider()
    agent = ClaimsAgent(
        tool_executor=tool_executor,
        prompt_manager=_build_prompt_manager(),
        llm_provider=llm_provider,
        knowledge_retriever=_build_knowledge_retriever(),
        grounder=Grounder(),
        tool_calling_orchestrator=ToolCallingOrchestrator(
            tool_registry=empty_registry, tool_executor=tool_executor, llm_provider=llm_provider
        ),
    )
    context = _seed_context(_ready_for_validation_state())

    response = await agent.handle(AgentRequest(message="here you go", user_id="user-1"), context)

    assert "could not find a policy" in response.response.lower()
    assert response.agent == "ClaimsAgent"

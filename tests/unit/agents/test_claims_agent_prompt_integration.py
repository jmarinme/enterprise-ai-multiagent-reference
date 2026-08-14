"""Unit tests specifically for ClaimsAgent's PromptManager injection (PBI-01-03): the agent
depends on PromptManager, never embeds prompt text, and surfaces the rendered prompt's
identifier/version — proving PromptManager was actually invoked.
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
    llm_provider = MockLLMProvider()
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


async def test_claims_agent_response_references_the_rendered_prompt_identifier_and_version() -> (
    None
):
    agent = _build_agent()
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    response = await agent.handle(
        AgentRequest(message="I need to file a claim", user_id="user-1"), context
    )

    assert "prompt=claims.system@3.3.0" in response.metadata["diagnostics"]


async def test_claims_agent_source_file_contains_no_embedded_prompt_wording() -> None:
    """The agent's own source must never hardcode the prompt's actual wording — only the
    logical identifier "claims.system" — proving prompt content evolves independently of
    Agent code."""
    agent_source = Path("src/agents/claims_agent.py").read_text(encoding="utf-8")
    prompt_source = Path("configs/prompts/claims/system.md").read_text(encoding="utf-8")

    prompt_body = prompt_source.split("---", 2)[2].strip()
    first_sentence = prompt_body.split(".")[0]

    assert first_sentence not in agent_source
    assert "claims.system" in agent_source

"""Unit tests specifically for ClaimsAgent's ToolCallingOrchestrator injection (PBI-02-04): the
LLM can request one of ClaimsAgent's allow-listed Tools and the outcome is surfaced as typed
AgentResponse.tool_calls, an LLM-requested Tool outside the allow-list is safely rejected, and
the deterministic business-fact text/ClaimsIntakeState are never affected either way — the
controlled Tool Calling step is purely additive, exactly like Grounding (PBI-02-03).
"""

from pathlib import Path

from src.agents.claims_agent import ClaimsAgent
from src.core.tool_calling.orchestrator import ToolCallingOrchestrator
from src.llm.mock_provider import MockLLMProvider
from src.llm.models import ToolCallArgument, ToolCallRequest
from src.prompts.filesystem_provider import FileSystemPromptProvider
from src.prompts.manager import PromptManager
from src.rag.grounder import Grounder
from src.rag.local_provider import LocalKnowledgeProvider
from src.rag.retriever import KnowledgeRetriever
from src.services.tools.adjuster_assignment_tool import AdjusterAssignmentTool
from src.services.tools.claim_registration_tool import ClaimRegistrationTool
from src.services.tools.claims_status_tool import ClaimsStatusTool
from src.services.tools.coverage_lookup_tool import CoverageLookupTool
from src.services.tools.customer_lookup_tool import CustomerLookupTool
from src.services.tools.lead_registration_tool import LeadRegistrationTool
from src.services.tools.payment_status_tool import PaymentStatusTool
from src.services.tools.policy_lookup_tool import PolicyLookupTool
from src.supervisor.models import AgentRequest, ConversationContext
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry, ToolRegistry


def _build_prompt_manager() -> PromptManager:
    return PromptManager(provider=FileSystemPromptProvider(prompts_root=Path("configs/prompts")))


def _build_knowledge_retriever() -> KnowledgeRetriever:
    return KnowledgeRetriever(
        provider=LocalKnowledgeProvider(documents_root=Path("configs/knowledge_base"))
    )


def _build_full_claims_tool_registry() -> InMemoryToolRegistry:
    """Registers every Tool src.core.tool_calling.policies.CLAIMS_ALLOWED_TOOLS names — required
    because ClaimsAgent always builds tool definitions for its full allow-list every turn."""
    registry = InMemoryToolRegistry()
    registry.register(CustomerLookupTool())
    registry.register(PolicyLookupTool())
    registry.register(ClaimsStatusTool())
    registry.register(PaymentStatusTool())
    registry.register(CoverageLookupTool())
    registry.register(ClaimRegistrationTool())
    registry.register(AdjusterAssignmentTool())
    return registry


def _build_agent(tool_registry: ToolRegistry, tool_call_plan: list[ToolCallRequest]) -> ClaimsAgent:
    tool_executor = ToolExecutor(tool_registry=tool_registry)
    llm_provider = MockLLMProvider(tool_call_plan=tool_call_plan)
    return ClaimsAgent(
        tool_executor=tool_executor,
        prompt_manager=_build_prompt_manager(),
        llm_provider=llm_provider,
        knowledge_retriever=_build_knowledge_retriever(),
        grounder=Grounder(),
        tool_calling_orchestrator=ToolCallingOrchestrator(
            tool_registry=tool_registry, tool_executor=tool_executor, llm_provider=llm_provider
        ),
    )


async def test_agent_surfaces_a_successful_llm_requested_tool_call() -> None:
    tool_registry = _build_full_claims_tool_registry()
    agent = _build_agent(
        tool_registry,
        tool_call_plan=[
            ToolCallRequest(
                call_id="call-1",
                tool_name="policy_lookup",
                arguments=[ToolCallArgument(name="policy_number", value="SYN-POL-0001")],
            )
        ],
    )
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    response = await agent.handle(
        AgentRequest(message="I need to report a claim", user_id="user-1"), context
    )

    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool_name == "policy_lookup"
    assert response.tool_calls[0].success is True


async def test_agent_never_offers_or_executes_a_tool_outside_its_allow_list() -> None:
    """lead_registration is a real, registered Tool — just not in
    src.core.tool_calling.policies.CLAIMS_ALLOWED_TOOLS. Even when the (scripted, test-only)
    LLM is instructed to request it, ClaimsAgent's own allow-list means it is never among the
    tool definitions offered to the LLM in the first place, so it is never requested and never
    executed — the deeper case of an LLM ignoring what was offered and requesting an
    unauthorized tool anyway is covered at the orchestrator level (see
    tests/unit/core/tool_calling/test_orchestrator.py::
    test_run_rejects_an_unauthorized_tool_call_without_executing_it), which uses a
    non-cooperative test double precisely because MockLLMProvider itself never does that."""
    tool_registry = _build_full_claims_tool_registry()
    tool_registry.register(LeadRegistrationTool())
    agent = _build_agent(
        tool_registry,
        tool_call_plan=[
            ToolCallRequest(call_id="call-1", tool_name="lead_registration", arguments=[])
        ],
    )
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    response = await agent.handle(
        AgentRequest(message="I need to report a claim", user_id="user-1"), context
    )

    assert response.tool_calls == []


async def test_tool_calling_never_alters_the_deterministic_business_fact_text() -> None:
    """The business-fact portion of the response (before the [prompt=...]/[llm=...]
    annotations) must be byte-identical whether or not a Tool call was requested via the
    controlled Tool Calling step — it is an additive capability, never a business fact source
    (CLAUDE.md §3)."""
    tool_registry = _build_full_claims_tool_registry()
    message = "I need to report a claim"

    with_tool_call = await _build_agent(
        tool_registry,
        tool_call_plan=[
            ToolCallRequest(
                call_id="call-1",
                tool_name="policy_lookup",
                arguments=[ToolCallArgument(name="policy_number", value="SYN-POL-0001")],
            )
        ],
    ).handle(
        AgentRequest(message=message, user_id="user-1"),
        ConversationContext(conversation_id="conv-1", user_id="user-1"),
    )
    without_tool_call = await _build_agent(tool_registry, tool_call_plan=[]).handle(
        AgentRequest(message=message, user_id="user-1"),
        ConversationContext(conversation_id="conv-1", user_id="user-1"),
    )

    business_fact_text_with = with_tool_call.response.split(" [prompt=")[0]
    business_fact_text_without = without_tool_call.response.split(" [prompt=")[0]
    assert business_fact_text_with == business_fact_text_without


async def test_tool_calling_error_degrades_gracefully_without_blocking_the_turn() -> None:
    """An allow-listed tool that is not actually registered (a configuration bug) must not
    block the turn — ClaimsAgent degrades to empty tool_calls, exactly like a Knowledge/Prompt/
    LLM failure already does."""
    empty_registry = InMemoryToolRegistry()  # none of CLAIMS_ALLOWED_TOOLS registered
    agent = _build_agent(empty_registry, tool_call_plan=[])
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    response = await agent.handle(
        AgentRequest(message="I need to report a claim", user_id="user-1"), context
    )

    assert response.tool_calls == []
    assert "traceback" not in response.response.lower()
    assert "exception" not in response.response.lower()

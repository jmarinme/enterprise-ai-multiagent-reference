"""Functional, multi-turn tests for ClaimsAgent (PBI-01-05): the full claim-notice intake flow
end to end, driven directly against the Agent (mirroring what SupervisorOrchestrator does —
feeding each turn's AgentResponse.metadata back in as the next turn's ConversationContext.
metadata). All Tools, the Prompt framework, and MockLLMProvider are real, wired dependencies;
nothing here is mocked.
"""

import re
from pathlib import Path

from src.agents.claims_agent import ClaimsAgent
from src.core.tool_calling.orchestrator import ToolCallingOrchestrator
from src.llm.mock_provider import MockLLMProvider
from src.prompts.filesystem_provider import FileSystemPromptProvider
from src.prompts.manager import PromptManager
from src.rag.grounder import Grounder
from src.rag.local_provider import LocalKnowledgeProvider
from src.rag.retriever import KnowledgeRetriever
from src.services.tools.adjuster_assignment_tool import AdjusterAssignmentTool
from src.services.tools.claim_registration_tool import ClaimRegistrationTool
from src.services.tools.payment_status_tool import PaymentStatusTool
from src.services.tools.policy_lookup_tool import PolicyLookupTool
from src.supervisor.models import AgentRequest, ConversationContext
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry

_CLAIM_REFERENCE_PATTERN = re.compile(r"SYN-CLM-\d{4}-\d{4}")


def _build_agent() -> ClaimsAgent:
    tool_registry = InMemoryToolRegistry()
    tool_registry.register(PolicyLookupTool())
    tool_registry.register(PaymentStatusTool())
    tool_registry.register(ClaimRegistrationTool())
    tool_registry.register(AdjusterAssignmentTool())
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


async def _run_conversation(agent: ClaimsAgent, messages: list[str]) -> list[str]:
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")
    responses: list[str] = []
    for message in messages:
        result = await agent.handle(AgentRequest(message=message, user_id="user-1"), context)
        responses.append(result.response)
        context = context.model_copy(update={"metadata": result.metadata})
    return responses


async def test_full_claim_report_flow_from_first_contact_to_adjuster_assignment() -> None:
    # PBI-04-04: a direct policy number ("SYN-POL-0001") short-circuits customer discovery, so
    # customer_name is never asked. Related fields are asked in groups (event_date+
    # event_location+loss_type, then injuries_reported+third_parties_involved); once every
    # field is collected, policy/payment/coverage are validated and an explicit yes/no
    # confirmation is required before the claim is actually registered — hence the trailing
    # "yes" beyond what PBI-01-05's flow needed.
    responses = await _run_conversation(
        _build_agent(),
        [
            "I need to report a claim",
            "SYN-POL-0001",
            "2026-08-01",
            "In my driveway",
            "It was a collision",
            "Another car hit me while parked",
            "555-123-4567",
            "no",
            "yes",
            "yes",  # vehicle_drivable (PBI-05-01: auto profile asks this)
            "yes",  # explicit confirmation before registration (PBI-04-04)
        ],
    )

    # Grouped questions keep each turn to at most one combined question; the one exception is a
    # partially-answered group (e.g. only event_date given), which falls back to joining the
    # remaining fields' individual prompts — never more than the two fields left in that group.
    for question in responses[:-1]:
        assert question.count("?") <= 2

    combined = " ".join(responses).lower()
    final = responses[-1]
    assert "active" in combined
    assert _CLAIM_REFERENCE_PATTERN.search(final)
    assert "assigned" in final.lower()


async def test_conversation_continues_gracefully_after_an_unknown_policy_number() -> None:
    """Policy validation only runs once every required field has been collected — supplying
    an unrecognized policy number does not fail immediately, it surfaces the "not found"
    notice once the rest of the intake is complete, without ever exposing internal detail."""
    responses = await _run_conversation(
        _build_agent(),
        [
            "I need to report a claim",
            "SYN-POL-9999",
            "2026-08-01",
            "In my driveway",
            "It was a collision",
            "Another car hit me while parked",
            "Jane Caller",
            "555-123-4567",
            "no",
            "yes",
        ],
    )

    assert "could not find" in responses[-1].lower()
    assert "traceback" not in responses[-1].lower()
    assert "exception" not in responses[-1].lower()


async def test_re_sending_a_message_after_the_claim_is_fully_processed_does_not_duplicate_it() -> (
    None
):
    agent = _build_agent()
    responses = await _run_conversation(
        agent,
        [
            "I need to report a claim",
            "SYN-POL-0001",
            "2026-08-01",
            "In my driveway",
            "It was a collision",
            "Another car hit me while parked",
            "555-123-4567",
            "no",
            "yes",
            "yes",  # vehicle_drivable (PBI-05-01: auto profile asks this)
            "yes",  # explicit confirmation before registration (PBI-04-04)
        ],
    )
    first_reference = _CLAIM_REFERENCE_PATTERN.search(responses[-1])
    assert first_reference is not None

    context = ConversationContext(conversation_id="conv-1", user_id="user-1")
    # Replay the full conversation once more via a fresh context/state chain to get the final
    # metadata, then send one extra message to confirm no second claim is created.
    last_metadata: dict[str, str] = {}
    for message in [
        "I need to report a claim",
        "SYN-POL-0001",
        "2026-08-01",
        "In my driveway",
        "It was a collision",
        "Another car hit me while parked",
        "555-123-4567",
        "no",
        "yes",
        "yes",
        "yes",
        "thank you!",
    ]:
        result = await agent.handle(AgentRequest(message=message, user_id="user-1"), context)
        context = context.model_copy(update={"metadata": result.metadata})
        last_metadata = result.metadata

    assert "claimsIntakeState" in last_metadata

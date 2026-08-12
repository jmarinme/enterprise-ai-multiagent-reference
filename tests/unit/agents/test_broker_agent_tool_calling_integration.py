"""Unit tests for BrokerAgent's ToolCallingOrchestrator injection (PBI-12-04, generalizing
PBI-02-04's ClaimsAgent-only wiring — see
docs/Architecture/adr/0011-react-pattern-for-tool-orchestrated-reasoning.md): the LLM can
request one of BrokerAgent's allow-listed Tools and the outcome is surfaced as typed
AgentResponse.tool_calls, an LLM-requested Tool outside the allow-list is safely rejected, the
deterministic business-fact text/BrokerInquiryState are never affected either way, and the
isolated ReAct path's own internal reasoning never leaks into the visible response or persisted
metadata — mirrors tests/unit/agents/test_claims_agent_tool_calling_integration.py's structure
and assertions for the second Agent this pattern was generalized to.
"""

from pathlib import Path

from src.agents.broker_agent import BrokerAgent
from src.core.tool_calling.orchestrator import ToolCallingOrchestrator
from src.llm.mock_provider import MockLLMProvider
from src.llm.models import (
    LLMRequest,
    LLMResponse,
    ToolCallArgument,
    ToolCallRequest,
)
from src.prompts.filesystem_provider import FileSystemPromptProvider
from src.prompts.manager import PromptManager
from src.services.tools.broker_account_lookup_tool import BrokerAccountLookupTool
from src.services.tools.broker_lookup_tool import BrokerLookupTool
from src.services.tools.commission_lookup_tool import CommissionLookupTool
from src.services.tools.commission_payment_request_tool import CommissionPaymentRequestTool
from src.services.tools.commission_periods_lookup_tool import CommissionPeriodsLookupTool
from src.services.tools.lead_registration_tool import LeadRegistrationTool
from src.services.tools.payment_status_tool import PaymentStatusTool
from src.services.tools.policy_lookup_tool import PolicyLookupTool
from src.services.tools.transaction_status_tool import TransactionStatusTool
from src.supervisor.models import AgentRequest, ConversationContext
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry, ToolRegistry


def _build_prompt_manager() -> PromptManager:
    return PromptManager(provider=FileSystemPromptProvider(prompts_root=Path("configs/prompts")))


def _build_full_broker_tool_registry() -> InMemoryToolRegistry:
    """Registers every Tool src.core.tool_calling.policies.BROKER_ALLOWED_TOOLS names —
    required because BrokerAgent always builds tool definitions for its full allow-list every
    turn."""
    registry = InMemoryToolRegistry()
    registry.register(BrokerLookupTool())
    registry.register(BrokerAccountLookupTool())
    registry.register(PolicyLookupTool())
    registry.register(TransactionStatusTool())
    registry.register(CommissionLookupTool())
    registry.register(CommissionPeriodsLookupTool())
    registry.register(CommissionPaymentRequestTool())
    registry.register(PaymentStatusTool())
    return registry


def _build_agent(
    tool_registry: ToolRegistry, tool_call_plan: list[ToolCallRequest], llm_provider: object = None
) -> BrokerAgent:
    tool_executor = ToolExecutor(tool_registry=tool_registry)
    llm = llm_provider or MockLLMProvider(tool_call_plan=tool_call_plan)
    return BrokerAgent(
        tool_executor=tool_executor,
        prompt_manager=_build_prompt_manager(),
        llm_provider=llm,
        tool_calling_orchestrator=ToolCallingOrchestrator(
            tool_registry=tool_registry, tool_executor=tool_executor, llm_provider=llm
        ),
    )


async def test_agent_surfaces_a_successful_llm_requested_tool_call() -> None:
    tool_registry = _build_full_broker_tool_registry()
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
        AgentRequest(message="I want to know the status of a policy.", user_id="user-1"), context
    )

    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool_name == "policy_lookup"
    assert response.tool_calls[0].success is True


async def test_agent_never_offers_or_executes_a_tool_outside_its_allow_list() -> None:
    """lead_registration is a real, registered Tool — just not in
    src.core.tool_calling.policies.BROKER_ALLOWED_TOOLS. Even when the (scripted, test-only)
    LLM is instructed to request it, BrokerAgent's own allow-list means it is never among the
    tool definitions offered to the LLM in the first place."""
    tool_registry = _build_full_broker_tool_registry()
    tool_registry.register(LeadRegistrationTool())
    agent = _build_agent(
        tool_registry,
        tool_call_plan=[
            ToolCallRequest(call_id="call-1", tool_name="lead_registration", arguments=[])
        ],
    )
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    response = await agent.handle(
        AgentRequest(message="I want to know the status of a policy.", user_id="user-1"), context
    )

    assert response.tool_calls == []


async def test_tool_calling_never_alters_the_deterministic_business_fact_text() -> None:
    """The business-fact portion of the response (before the [prompt=...]/[llm=...]
    annotations) must be byte-identical whether or not a Tool call was requested via the
    controlled Tool Calling step — it is an additive capability, never a business fact source
    (CLAUDE.md §3)."""
    tool_registry = _build_full_broker_tool_registry()
    message = "I want to know the status of a policy."

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
    block the turn — BrokerAgent degrades to empty tool_calls, exactly like ClaimsAgent."""
    empty_registry = InMemoryToolRegistry()  # none of BROKER_ALLOWED_TOOLS registered
    agent = _build_agent(empty_registry, tool_call_plan=[])
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    response = await agent.handle(
        AgentRequest(message="I want to know the status of a policy.", user_id="user-1"), context
    )

    assert response.tool_calls == []
    assert "traceback" not in response.response.lower()
    assert "exception" not in response.response.lower()


async def test_multiple_sequential_tool_calls_are_bounded_by_max_iterations_through_the_agent() -> (
    None
):
    """End-to-end proof (through the real Agent, not just the orchestrator directly) that a
    misbehaving/verbose LLM's sequential tool requests are still bounded by max_iterations —
    default 3 (src.core.tool_calling.models.DEFAULT_MAX_TOOL_CALL_ITERATIONS), matching what
    ClaimsAgent already relies on."""

    class _SequentialToolCallProvider:
        def __init__(self) -> None:
            self.call_count = 0

        async def generate(self, request: LLMRequest) -> LLMResponse:
            self.call_count += 1
            return LLMResponse(
                text="",
                model="stub",
                tool_calls=[
                    ToolCallRequest(
                        call_id=f"call-{self.call_count}",
                        tool_name="policy_lookup",
                        arguments=[
                            ToolCallArgument(name="policy_number", value=f"SYN-POL-{self.call_count:04d}")
                        ],
                    )
                ],
            )

    tool_registry = _build_full_broker_tool_registry()
    llm_provider = _SequentialToolCallProvider()
    agent = _build_agent(tool_registry, tool_call_plan=[], llm_provider=llm_provider)
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    response = await agent.handle(
        AgentRequest(message="I want to know the status of a policy.", user_id="user-1"), context
    )

    # Default max_iterations=3, a genuinely different policy number each time — none of the
    # three is ever flagged as a duplicate (only SYN-POL-0001 is a real synthetic policy, so
    # the other two legitimately fail lookup — that is a business-data outcome, not a
    # duplicate-detection or iteration-bound failure, which is what this test verifies).
    assert len(response.tool_calls) == 3
    assert all(call.error_type != "duplicate_call" for call in response.tool_calls)


# --- reasoning isolation (PBI-12-04) ------------------------------------------------------------


class _ReasoningLeakingLLMProvider:
    """A scripted double whose text response looks exactly like leaked chain-of-thought — used
    to prove that text is structurally discarded by _run_controlled_tool_calling, never
    surfaced to the user or persisted, regardless of what an LLM might return."""

    async def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            text=(
                "Thought: I should call policy_lookup because the user is asking about their "
                "policy. Observation: the tool returned an active status. Final Answer: ready."
            ),
            model="stub",
        )


async def test_isolated_tool_calling_reasoning_text_never_leaks_into_the_visible_response() -> (
    None
):
    tool_registry = _build_full_broker_tool_registry()
    agent = _build_agent(
        tool_registry, tool_call_plan=[], llm_provider=_ReasoningLeakingLLMProvider()
    )
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    response = await agent.handle(
        AgentRequest(message="I want to know the status of a policy.", user_id="user-1"), context
    )

    assert "Thought:" not in response.response
    assert "Observation:" not in response.response
    assert "Final Answer:" not in response.response


async def test_isolated_tool_calling_reasoning_text_is_never_persisted_in_metadata() -> None:
    """CLAUDE.md §10: hidden chain-of-thought must never be persisted. Only the final answer,
    the typed tool-call audit (ToolCallResult — no free-text reasoning field exists on that
    model), and the pre-existing metadata keys may be stored."""
    tool_registry = _build_full_broker_tool_registry()
    agent = _build_agent(
        tool_registry, tool_call_plan=[], llm_provider=_ReasoningLeakingLLMProvider()
    )
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    response = await agent.handle(
        AgentRequest(message="I want to know the status of a policy.", user_id="user-1"), context
    )

    for value in response.metadata.values():
        assert "Thought:" not in value
        assert "Observation:" not in value

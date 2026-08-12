"""Functional, multi-turn tests for BrokerAgent (PBI-01-06): the full broker-services flow end
to end, driven directly against the Agent (mirroring what SupervisorOrchestrator does — feeding
each turn's AgentResponse.metadata back in as the next turn's ConversationContext.metadata).
All Tools, the Prompt framework, and MockLLMProvider are real, wired dependencies except where
a stub Prompt/LLM provider is used to prove graceful degradation on failure.
"""

import re
from pathlib import Path

import pytest

from src.agents.broker_agent import BrokerAgent
from src.core.tool_calling.orchestrator import ToolCallingOrchestrator
from src.llm.exceptions import LLMProviderError
from src.llm.mock_provider import MockLLMProvider
from src.llm.models import LLMRequest, LLMResponse
from src.prompts.exceptions import PromptNotFoundError
from src.prompts.filesystem_provider import FileSystemPromptProvider
from src.prompts.manager import PromptManager
from src.prompts.models import PromptRenderContext, RenderedPrompt
from src.services.tools.broker_account_lookup_tool import BrokerAccountLookupTool
from src.services.tools.commission_lookup_tool import CommissionLookupTool
from src.services.tools.commission_payment_request_tool import CommissionPaymentRequestTool
from src.services.tools.payment_status_tool import PaymentStatusTool
from src.services.tools.policy_lookup_tool import PolicyLookupTool
from src.services.tools.transaction_status_tool import TransactionStatusTool
from src.supervisor.models import AgentRequest, ConversationContext
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry

_PAYMENT_REQUEST_REFERENCE_PATTERN = re.compile(r"SYN-PAYREQ-\d{4}-\d{4}")


def _build_prompt_manager() -> PromptManager:
    return PromptManager(provider=FileSystemPromptProvider(prompts_root=Path("configs/prompts")))


def _build_agent() -> BrokerAgent:
    tool_registry = InMemoryToolRegistry()
    tool_registry.register(PolicyLookupTool())
    tool_registry.register(PaymentStatusTool())
    tool_registry.register(BrokerAccountLookupTool())
    tool_registry.register(TransactionStatusTool())
    tool_registry.register(CommissionLookupTool())
    tool_registry.register(CommissionPaymentRequestTool())
    tool_executor = ToolExecutor(tool_registry=tool_registry)
    llm_provider = MockLLMProvider()
    return BrokerAgent(
        tool_executor=tool_executor,
        prompt_manager=_build_prompt_manager(),
        llm_provider=llm_provider,
        tool_calling_orchestrator=ToolCallingOrchestrator(
            tool_registry=tool_registry, tool_executor=tool_executor, llm_provider=llm_provider
        ),
    )


async def _run_conversation(agent: BrokerAgent, messages: list[str]) -> list[str]:
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")
    responses: list[str] = []
    for message in messages:
        result = await agent.handle(AgentRequest(message=message, user_id="user-1"), context)
        responses.append(result.response)
        context = context.model_copy(update={"metadata": result.metadata})
    return responses


async def test_full_policy_status_conversation() -> None:
    responses = await _run_conversation(
        _build_agent(),
        ["I want to know the status of a policy.", "SYN-POL-0001"],
    )

    assert "please provide the synthetic policy number" in responses[0].lower()
    assert "active" in responses[-1].lower()
    assert "up to date" in responses[-1].lower()


async def test_full_commission_conversation_with_a_successful_payment_request() -> None:
    responses = await _run_conversation(
        _build_agent(),
        [
            "I need to check my commissions.",
            "SYN-BRK-0001 2026-Q1",
            "yes",
        ],
    )

    assert "brokerage" in responses[0].lower() and "period" in responses[0].lower()
    assert "available" in responses[1].lower()
    assert _PAYMENT_REQUEST_REFERENCE_PATTERN.search(responses[-1])


async def test_conversation_continues_gracefully_after_an_unknown_broker() -> None:
    responses = await _run_conversation(
        _build_agent(),
        ["I need to check my commissions.", "SYN-BRK-9999 2026-Q1"],
    )

    assert "could not find a broker" in responses[-1].lower()
    assert "traceback" not in responses[-1].lower()
    assert "exception" not in responses[-1].lower()


async def test_agent_degrades_gracefully_when_a_tool_is_not_registered() -> None:
    empty_registry = InMemoryToolRegistry()
    empty_tool_executor = ToolExecutor(tool_registry=empty_registry)
    empty_llm_provider = MockLLMProvider()
    agent = BrokerAgent(
        tool_executor=empty_tool_executor,
        prompt_manager=_build_prompt_manager(),
        llm_provider=empty_llm_provider,
        tool_calling_orchestrator=ToolCallingOrchestrator(
            tool_registry=empty_registry,
            tool_executor=empty_tool_executor,
            llm_provider=empty_llm_provider,
        ),
    )

    responses = await _run_conversation(
        agent, ["I want to know the status of a policy.", "SYN-POL-0001"]
    )

    assert "could not find a policy" in responses[-1].lower()
    assert responses[-1]


class _RaisingPromptManager:
    async def render(
        self, identifier: str, context: PromptRenderContext
    ) -> RenderedPrompt:
        raise PromptNotFoundError(identifier)


class _RaisingLLMProvider:
    async def generate(self, request: LLMRequest) -> LLMResponse:
        raise LLMProviderError("stub", "simulated outage")


async def test_agent_degrades_gracefully_when_prompt_manager_fails() -> None:
    tool_registry = InMemoryToolRegistry()
    tool_registry.register(PolicyLookupTool())
    tool_registry.register(PaymentStatusTool())
    tool_executor = ToolExecutor(tool_registry=tool_registry)
    llm_provider = MockLLMProvider()
    agent = BrokerAgent(
        tool_executor=tool_executor,
        prompt_manager=_RaisingPromptManager(),  # type: ignore[arg-type]
        llm_provider=llm_provider,
        tool_calling_orchestrator=ToolCallingOrchestrator(
            tool_registry=tool_registry, tool_executor=tool_executor, llm_provider=llm_provider
        ),
    )
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    response = await agent.handle(
        AgentRequest(message="I want to know the status of a policy.", user_id="user-1"), context
    )

    assert "please provide the synthetic policy number" in response.response.lower()
    assert "[prompt=" not in response.response


async def test_agent_degrades_gracefully_when_llm_provider_fails() -> None:
    tool_registry = InMemoryToolRegistry()
    tool_registry.register(PolicyLookupTool())
    tool_registry.register(PaymentStatusTool())
    raising_llm_provider = _RaisingLLMProvider()
    agent = BrokerAgent(
        tool_executor=ToolExecutor(tool_registry=tool_registry),
        prompt_manager=_build_prompt_manager(),
        llm_provider=raising_llm_provider,
        # Proves the PBI-12-04 hardening (broad `except Exception` around the isolated
        # tool-calling path, see broker_agent.py): a genuine LLMProvider failure — not just a
        # ToolCallingError — inside _run_controlled_tool_calling must also degrade gracefully,
        # not propagate past this Agent and crash the whole turn.
        tool_calling_orchestrator=ToolCallingOrchestrator(
            tool_registry=tool_registry,
            tool_executor=ToolExecutor(tool_registry=tool_registry),
            llm_provider=raising_llm_provider,
        ),
    )
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    response = await agent.handle(
        AgentRequest(message="I want to know the status of a policy.", user_id="user-1"), context
    )

    assert "please provide the synthetic policy number" in response.response.lower()
    assert "[prompt=broker.system@2.1.0]" in response.metadata["diagnostics"]
    assert "[llm=" not in response.metadata["diagnostics"]


@pytest.mark.parametrize(
    ("message", "expected_substring"),
    [
        # "hello there" carries a clear English signal ("hello"); "good morning" carries none of
        # the deliberately small English/Spanish signal-word lists (src.agents.shared.language),
        # so it resolves to this platform's Spanish-first default — both are still "ambiguous"
        # in the sense of not naming policy/transaction/commission, just in different languages.
        ("hello there", "what would you like help with"),
        ("good morning", "en qué te puedo ayudar"),
    ],
)
async def test_ambiguous_first_message_asks_which_kind_of_help_is_needed(
    message: str, expected_substring: str
) -> None:
    agent = _build_agent()
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    response = await agent.handle(AgentRequest(message=message, user_id="user-1"), context)

    assert expected_substring in response.response.lower()

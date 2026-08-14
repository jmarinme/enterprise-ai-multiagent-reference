"""PBI-14-03 section 15 regression scenario: a single compound message naming both the broker
(by name, not a typed ID) and the commission period must resolve BOTH in one turn — never a
form-style "what's your broker name?" followed by "which period?" — and the shared confirmation
module must understand "va" (not the literal word "sí") when offering the payment request.
"""

from pathlib import Path

from src.agents.broker_agent import BrokerAgent
from src.core.tool_calling.orchestrator import ToolCallingOrchestrator
from src.llm.mock_provider import MockLLMProvider
from src.prompts.filesystem_provider import FileSystemPromptProvider
from src.prompts.manager import PromptManager
from src.services.tools.broker_account_lookup_tool import BrokerAccountLookupTool
from src.services.tools.broker_lookup_tool import BrokerLookupTool
from src.services.tools.commission_lookup_tool import CommissionLookupTool
from src.services.tools.commission_payment_request_tool import CommissionPaymentRequestTool
from src.services.tools.commission_periods_lookup_tool import CommissionPeriodsLookupTool
from src.services.tools.payment_status_tool import PaymentStatusTool
from src.services.tools.policy_lookup_tool import PolicyLookupTool
from src.services.tools.transaction_status_tool import TransactionStatusTool
from src.supervisor.models import AgentRequest, ConversationContext
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry

_SCHEMA_NAME = "broker_semantic_interpretation"
_MINIMAL_INTERPRETATION = '{"intent": "broker", "intent_confidence": 0.9}'


def _build_agent() -> BrokerAgent:
    tool_registry = InMemoryToolRegistry()
    tool_registry.register(PolicyLookupTool())
    tool_registry.register(PaymentStatusTool())
    tool_registry.register(BrokerAccountLookupTool())
    tool_registry.register(BrokerLookupTool())
    tool_registry.register(TransactionStatusTool())
    tool_registry.register(CommissionLookupTool())
    tool_registry.register(CommissionPeriodsLookupTool())
    tool_registry.register(CommissionPaymentRequestTool())
    tool_executor = ToolExecutor(tool_registry=tool_registry)
    llm_provider = MockLLMProvider(
        structured_response_sequence={_SCHEMA_NAME: [_MINIMAL_INTERPRETATION] * 5}
    )
    prompt_manager = PromptManager(
        provider=FileSystemPromptProvider(prompts_root=Path("configs/prompts"))
    )
    return BrokerAgent(
        tool_executor=tool_executor,
        prompt_manager=prompt_manager,
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


async def test_compound_broker_name_and_period_message_skips_the_second_question() -> None:
    agent = _build_agent()

    responses = await _run_conversation(
        agent,
        [
            # Compound: names the brokerage (not a typed ID) AND the commission period in one
            # natural sentence — both fields must resolve from this single turn.
            "Soy Synthetic Brokerage One y quiero revisar mis comisiones del primer trimestre de 2026",
            "va",
        ],
    )

    first_response = responses[0].lower()
    # The compound message must not be met with a second, separate question for whichever
    # field it already supplied — it goes straight to the commission summary.
    assert "período" not in first_response and "period" not in first_response
    assert "1,250" in responses[0] or "1250" in responses[0]
    assert "would you like to request payment" in first_response or "solicitar el pago" in first_response

    # Shared confirmation understanding: "va" (not the literal "sí") registers the payment
    # request.
    final = responses[-1]
    assert "SYN-PAYREQ-" in final

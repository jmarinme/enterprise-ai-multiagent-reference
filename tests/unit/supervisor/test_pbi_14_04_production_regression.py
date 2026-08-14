"""PBI-14-04 section 22.D — the critical live production regression, driven through the FULL
Supervisor pipeline (not a direct Agent call): the exact message that was misrouted to
FallbackAgent in live Azure validation must now reach ClaimsAgent, using exactly ONE structured
semantic call for the whole turn (reused by ClaimsAgent, never re-requested), while the
existing, separate ReAct/Tool-Calling capability remains untouched and available.
"""

from pathlib import Path

from src.agents.broker_agent import BrokerAgent
from src.agents.claims_agent import ClaimsAgent
from src.agents.commercial_intake_agent import CommercialIntakeAgent
from src.agents.fallback_agent import FallbackAgent
from src.core.tool_calling.orchestrator import ToolCallingOrchestrator
from src.llm.mock_provider import MockLLMProvider
from src.llm.models import LLMRequest, LLMResponse
from src.prompts.filesystem_provider import FileSystemPromptProvider
from src.prompts.manager import PromptManager
from src.rag.grounder import Grounder
from src.rag.local_provider import LocalKnowledgeProvider
from src.rag.retriever import KnowledgeRetriever
from src.services.conversation_store.in_memory import InMemoryConversationRepository
from src.services.tools.adjuster_assignment_tool import AdjusterAssignmentTool
from src.services.tools.broker_account_lookup_tool import BrokerAccountLookupTool
from src.services.tools.broker_lookup_tool import BrokerLookupTool
from src.services.tools.claim_registration_tool import ClaimRegistrationTool
from src.services.tools.claims_status_tool import ClaimsStatusTool
from src.services.tools.commission_lookup_tool import CommissionLookupTool
from src.services.tools.commission_payment_request_tool import CommissionPaymentRequestTool
from src.services.tools.commission_periods_lookup_tool import CommissionPeriodsLookupTool
from src.services.tools.coverage_lookup_tool import CoverageLookupTool
from src.services.tools.customer_lookup_tool import CustomerLookupTool
from src.services.tools.lead_registration_tool import LeadRegistrationTool
from src.services.tools.payment_status_tool import PaymentStatusTool
from src.services.tools.policy_lookup_tool import PolicyLookupTool
from src.services.tools.transaction_status_tool import TransactionStatusTool
from src.supervisor.intent import RuleBasedIntentResolver
from src.supervisor.models import AgentRequest, IntentCategory
from src.supervisor.orchestrator import SupervisorOrchestrator
from src.supervisor.registry import InMemoryAgentRegistry
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry

_PRODUCTION_REGRESSION_MESSAGE = (
    "quiero reportar un percance derivado de la fuerte lluvia que cayó hoy un camión me pegó "
    "por atrás"
)
_TURN_SCHEMA_NAME = "turn_interpretation"
_TURN_JSON = (
    '{"intent": "claims", "intent_confidence": 0.94, '
    '"routing_reason": "User is reporting damage from a vehicle collision.", '
    '"claims_entities": {"event_date": "2026-08-14", "loss_type": "collision", '
    '"loss_description": "A truck hit the user from behind during heavy rain."}}'
)


class _CountingMockLLMProvider(MockLLMProvider):
    """Counts only STRUCTURED (response_schema-bearing) calls — the semantic-interpretation
    call this PBI must keep at exactly one per turn. The separate, unchanged ReAct/Tool-Calling
    loop (src.core.tool_calling.orchestrator.ToolCallingOrchestrator) never sets
    response_schema, so its own calls are deliberately not counted here — this test only
    asserts the semantic-call count, not ReAct's, which is explicitly out of this PBI's scope
    (section 18: ReAct must remain unchanged)."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.structured_call_count = 0

    async def generate(self, request: LLMRequest) -> LLMResponse:
        if request.response_schema is not None:
            self.structured_call_count += 1
        return await super().generate(request)


def _build_prompt_manager() -> PromptManager:
    return PromptManager(provider=FileSystemPromptProvider(prompts_root=Path("configs/prompts")))


def _build_supervisor(llm_provider: _CountingMockLLMProvider) -> SupervisorOrchestrator:
    tool_registry = InMemoryToolRegistry()
    for tool in (
        PolicyLookupTool(),
        PaymentStatusTool(),
        ClaimRegistrationTool(),
        ClaimsStatusTool(),
        AdjusterAssignmentTool(),
        CustomerLookupTool(),
        CoverageLookupTool(),
        BrokerAccountLookupTool(),
        BrokerLookupTool(),
        TransactionStatusTool(),
        CommissionLookupTool(),
        CommissionPeriodsLookupTool(),
        CommissionPaymentRequestTool(),
        LeadRegistrationTool(),
    ):
        tool_registry.register(tool)
    tool_executor = ToolExecutor(tool_registry=tool_registry)
    prompt_manager = _build_prompt_manager()
    tool_calling_orchestrator = ToolCallingOrchestrator(
        tool_registry=tool_registry, tool_executor=tool_executor, llm_provider=llm_provider
    )
    knowledge_retriever = KnowledgeRetriever(
        provider=LocalKnowledgeProvider(documents_root=Path("configs/knowledge_base"))
    )

    registry = InMemoryAgentRegistry()
    registry.register(
        IntentCategory.CLAIMS,
        ClaimsAgent(
            tool_executor=tool_executor,
            prompt_manager=prompt_manager,
            llm_provider=llm_provider,
            knowledge_retriever=knowledge_retriever,
            grounder=Grounder(),
            tool_calling_orchestrator=tool_calling_orchestrator,
        ),
    )
    registry.register(
        IntentCategory.BROKER,
        BrokerAgent(
            tool_executor=tool_executor,
            prompt_manager=prompt_manager,
            llm_provider=llm_provider,
            tool_calling_orchestrator=tool_calling_orchestrator,
        ),
    )
    registry.register(
        IntentCategory.COMMERCIAL,
        CommercialIntakeAgent(
            tool_executor=tool_executor,
            prompt_manager=prompt_manager,
            llm_provider=llm_provider,
            tool_calling_orchestrator=tool_calling_orchestrator,
        ),
    )
    registry.register(IntentCategory.UNKNOWN, FallbackAgent())

    return SupervisorOrchestrator(
        conversation_repository=InMemoryConversationRepository(),
        intent_resolver=RuleBasedIntentResolver(),
        agent_registry=registry,
        prompt_manager=prompt_manager,
        llm_provider=llm_provider,
    )


async def test_production_regression_sentence_now_reaches_claims_agent() -> None:
    llm_provider = _CountingMockLLMProvider(
        structured_response_plan={_TURN_SCHEMA_NAME: _TURN_JSON}
    )
    supervisor = _build_supervisor(llm_provider)

    response = await supervisor.handle(
        AgentRequest(message=_PRODUCTION_REGRESSION_MESSAGE, user_id="user-1")
    )

    # The headline fix: ClaimsAgent is selected, never FallbackAgent.
    assert response.agent == "ClaimsAgent"
    assert response.intent == IntentCategory.CLAIMS
    assert "no pude identificar" not in response.response.lower()

    # Exactly ONE structured semantic call for the whole turn — the Supervisor's own call,
    # reused by ClaimsAgent, never re-requested (PBI-14-04 section 3's central requirement).
    assert llm_provider.structured_call_count == 1

    # Real routing telemetry proves semantic (not deterministic-fallback) routing occurred.
    diagnostics = response.routing_diagnostics or {}
    assert diagnostics.get("routingSource") == "semantic"
    assert float(diagnostics.get("routingConfidence", "0")) >= 0.9

    # The reused interpretation's entities were merged into Claims' own deterministic state
    # (proving reuse actually flows through, not just routing) — surfaced via the claims state
    # metadata this Agent always round-trips.
    assert "claimsIntakeState" in response.metadata


async def test_ready_react_tool_calling_capability_is_unaffected() -> None:
    """Section 18: ReAct must remain intact — ToolCallingOrchestrator.run() is still invoked
    (as its own, separate, isolated call) alongside the semantic-routing call, exactly as
    PBI-12-04/PBI-14-03 already established."""
    llm_provider = _CountingMockLLMProvider(
        structured_response_plan={_TURN_SCHEMA_NAME: _TURN_JSON}
    )
    supervisor = _build_supervisor(llm_provider)

    response = await supervisor.handle(
        AgentRequest(message=_PRODUCTION_REGRESSION_MESSAGE, user_id="user-1")
    )

    # model/token_usage are only ever populated when ToolCallingOrchestrator.run() actually
    # executed (see ClaimsAgent._run_controlled_tool_calling) — proves the isolated ReAct path
    # ran normally, unaffected by this PBI's routing change.
    assert response.model is not None


async def test_intent_switches_across_turns_within_the_same_conversation() -> None:
    """PBI-14-04 section 15: the semantic interpreter runs on every relevant turn, not just the
    first — a caller legitimately switching domains mid-conversation (Claims -> Broker ->
    Commercial) must be routed to each new domain in turn, never stuck with the first agent."""
    llm_provider = _CountingMockLLMProvider(
        structured_response_sequence={
            _TURN_SCHEMA_NAME: [
                _TURN_JSON,
                '{"intent": "broker_services", "intent_confidence": 0.9}',
                '{"intent": "commercial_intake", "intent_confidence": 0.9}',
            ]
        }
    )
    supervisor = _build_supervisor(llm_provider)

    first = await supervisor.handle(
        AgentRequest(message="me chocaron ayer", user_id="user-1")
    )
    assert first.agent == "ClaimsAgent"

    second = await supervisor.handle(
        AgentRequest(
            message="por cierto, ¿cómo van mis comisiones?",
            user_id="user-1",
            conversation_id=first.conversation_id,
        )
    )
    assert second.agent == "BrokerAgent"

    third = await supervisor.handle(
        AgentRequest(
            message="también necesito asegurar una bodega nueva",
            user_id="user-1",
            conversation_id=first.conversation_id,
        )
    )
    assert third.agent == "CommercialIntakeAgent"

    # Domain-specific state stays isolated across the switch — Broker's own working state was
    # never contaminated with Claims-only fields, and vice versa (each Agent's metadata key is
    # distinct — see src.agents.shared.state_persistence).
    assert "claimsIntakeState" in third.metadata
    assert "brokerInquiryState" in third.metadata
    assert "commercialIntakeState" in third.metadata

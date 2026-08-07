"""Unit tests for SupervisorOrchestrator: full pipeline, DI, and conversation persistence.

Uses InMemoryConversationRepository + RuleBasedIntentResolver + InMemoryAgentRegistry with
stub agents — 100% deterministic, no Azure dependency.
"""

from src.domain.conversation import MessageRole
from src.services.conversation_store.in_memory import InMemoryConversationRepository
from src.supervisor.intent import RuleBasedIntentResolver
from src.supervisor.models import (
    AgentRequest,
    AgentResponse,
    ConversationContext,
    IntentCategory,
    SupervisorConfig,
)
from src.supervisor.orchestrator import SupervisorOrchestrator
from src.supervisor.registry import InMemoryAgentRegistry


class _StubAgent:
    def __init__(self, name: str, intent: IntentCategory, reply: str) -> None:
        self.name = name
        self._intent = intent
        self._reply = reply
        self.received_requests: list[AgentRequest] = []

    async def handle(self, request: AgentRequest, context: ConversationContext) -> AgentResponse:
        self.received_requests.append(request)
        return AgentResponse(
            conversation_id=context.conversation_id,
            agent=self.name,
            intent=self._intent,
            response=self._reply,
        )


def _build_supervisor() -> tuple[SupervisorOrchestrator, InMemoryConversationRepository, dict]:
    repository = InMemoryConversationRepository()
    registry = InMemoryAgentRegistry()
    agents = {
        IntentCategory.CLAIMS: _StubAgent("ClaimsStub", IntentCategory.CLAIMS, "claims reply"),
        IntentCategory.BROKER: _StubAgent("BrokerStub", IntentCategory.BROKER, "broker reply"),
        IntentCategory.UNKNOWN: _StubAgent("FallbackStub", IntentCategory.UNKNOWN, "fallback reply"),
    }
    for intent, agent in agents.items():
        registry.register(intent, agent)

    supervisor = SupervisorOrchestrator(
        conversation_repository=repository,
        intent_resolver=RuleBasedIntentResolver(),
        agent_registry=registry,
    )
    return supervisor, repository, agents


async def test_handle_routes_to_the_registered_agent_for_the_resolved_intent() -> None:
    supervisor, _repository, agents = _build_supervisor()

    response = await supervisor.handle(
        AgentRequest(message="I need to file a claim", user_id="user-1")
    )

    assert response.agent == "ClaimsStub"
    assert response.intent == IntentCategory.CLAIMS
    assert agents[IntentCategory.CLAIMS].received_requests


async def test_handle_routes_different_intents_to_different_agents_without_branching() -> None:
    supervisor, _repository, _agents = _build_supervisor()

    claims_response = await supervisor.handle(
        AgentRequest(message="claim please", user_id="user-1")
    )
    broker_response = await supervisor.handle(
        AgentRequest(message="broker commission question", user_id="user-1")
    )

    assert claims_response.agent == "ClaimsStub"
    assert broker_response.agent == "BrokerStub"


async def test_handle_creates_a_new_conversation_on_first_turn() -> None:
    supervisor, repository, _agents = _build_supervisor()

    response = await supervisor.handle(
        AgentRequest(message="I need to file a claim", user_id="user-1")
    )

    stored = await repository.get_conversation("user-1", response.conversation_id)
    assert stored is not None
    assert len(stored.messages) == 2
    assert stored.messages[0].role == MessageRole.USER
    assert stored.messages[0].content == "I need to file a claim"
    assert stored.messages[1].role == MessageRole.ASSISTANT
    assert stored.messages[1].content == "claims reply"


async def test_handle_appends_to_an_existing_conversation_on_subsequent_turns() -> None:
    supervisor, repository, _agents = _build_supervisor()

    first = await supervisor.handle(AgentRequest(message="claim one", user_id="user-1"))
    await supervisor.handle(
        AgentRequest(
            message="claim two", user_id="user-1", conversation_id=first.conversation_id
        )
    )

    stored = await repository.get_conversation("user-1", first.conversation_id)
    assert stored is not None
    assert len(stored.messages) == 4
    assert [m.content for m in stored.messages] == [
        "claim one",
        "claims reply",
        "claim two",
        "claims reply",
    ]


async def test_handle_uses_unknown_agent_for_unmatched_messages() -> None:
    supervisor, _repository, agents = _build_supervisor()

    response = await supervisor.handle(AgentRequest(message="hello there", user_id="user-1"))

    assert response.agent == "FallbackStub"
    assert response.intent == IntentCategory.UNKNOWN
    assert agents[IntentCategory.UNKNOWN].received_requests


def test_supervisor_is_constructed_via_dependency_injection_not_globals() -> None:
    repository = InMemoryConversationRepository()
    registry = InMemoryAgentRegistry()
    resolver = RuleBasedIntentResolver()
    config = SupervisorConfig(max_history_messages=5)

    supervisor = SupervisorOrchestrator(
        conversation_repository=repository,
        intent_resolver=resolver,
        agent_registry=registry,
        config=config,
    )

    assert supervisor._conversation_repository is repository
    assert supervisor._intent_resolver is resolver
    assert supervisor._agent_registry is registry
    assert supervisor._config is config


def test_supervisor_uses_default_config_when_none_provided() -> None:
    supervisor = SupervisorOrchestrator(
        conversation_repository=InMemoryConversationRepository(),
        intent_resolver=RuleBasedIntentResolver(),
        agent_registry=InMemoryAgentRegistry(),
    )

    assert supervisor._config.max_history_messages == 20

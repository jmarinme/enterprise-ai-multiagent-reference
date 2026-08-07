"""Unit tests for InMemoryAgentRegistry: register, unregister, resolve, list."""

import pytest

from src.supervisor.exceptions import AgentNotFoundError
from src.supervisor.models import AgentRequest, AgentResponse, ConversationContext, IntentCategory
from src.supervisor.registry import InMemoryAgentRegistry


class _StubAgent:
    name = "StubAgent"

    async def handle(self, request: AgentRequest, context: ConversationContext) -> AgentResponse:
        return AgentResponse(
            conversation_id=context.conversation_id,
            agent=self.name,
            intent=IntentCategory.CLAIMS,
            response="stub",
        )


def test_register_and_resolve_returns_the_registered_agent() -> None:
    registry = InMemoryAgentRegistry()
    agent = _StubAgent()

    registry.register(IntentCategory.CLAIMS, agent)

    assert registry.resolve(IntentCategory.CLAIMS) is agent


def test_resolve_raises_agent_not_found_error_when_unregistered() -> None:
    registry = InMemoryAgentRegistry()

    with pytest.raises(AgentNotFoundError):
        registry.resolve(IntentCategory.BROKER)


def test_unregister_removes_the_agent() -> None:
    registry = InMemoryAgentRegistry()
    registry.register(IntentCategory.CLAIMS, _StubAgent())

    registry.unregister(IntentCategory.CLAIMS)

    with pytest.raises(AgentNotFoundError):
        registry.resolve(IntentCategory.CLAIMS)


def test_unregister_is_a_no_op_when_nothing_registered() -> None:
    registry = InMemoryAgentRegistry()

    registry.unregister(IntentCategory.COMMERCIAL)  # must not raise


def test_list_returns_all_registered_agents() -> None:
    registry = InMemoryAgentRegistry()
    claims_agent = _StubAgent()
    broker_agent = _StubAgent()

    registry.register(IntentCategory.CLAIMS, claims_agent)
    registry.register(IntentCategory.BROKER, broker_agent)

    assert set(registry.list()) == {claims_agent, broker_agent}


def test_register_overwrites_an_existing_entry_for_the_same_intent() -> None:
    registry = InMemoryAgentRegistry()
    first_agent = _StubAgent()
    second_agent = _StubAgent()

    registry.register(IntentCategory.CLAIMS, first_agent)
    registry.register(IntentCategory.CLAIMS, second_agent)

    assert registry.resolve(IntentCategory.CLAIMS) is second_agent
    assert len(registry.list()) == 1

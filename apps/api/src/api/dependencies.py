"""FastAPI dependency-injection wiring for the Supervisor orchestration framework.

This is the composition root: it is the one place that imports concrete Agent classes and
wires them into the registry. src/supervisor/ itself never imports any concrete agent —
adding a new agent means adding one line here, not touching the framework.
"""

from __future__ import annotations

from functools import lru_cache

from src.agents.broker_agent import BrokerAgent
from src.agents.claims_agent import ClaimsAgent
from src.agents.commercial_intake_agent import CommercialIntakeAgent
from src.agents.fallback_agent import FallbackAgent
from src.services.conversation_store.factory import get_conversation_repository
from src.supervisor.intent import RuleBasedIntentResolver
from src.supervisor.models import IntentCategory
from src.supervisor.orchestrator import SupervisorOrchestrator
from src.supervisor.registry import InMemoryAgentRegistry

from src.config.settings import ConversationStoreSettings


@lru_cache
def get_supervisor() -> SupervisorOrchestrator:
    """Build and cache the process-wide Supervisor instance."""
    conversation_store_settings = ConversationStoreSettings()
    repository = get_conversation_repository(conversation_store_settings)

    registry = InMemoryAgentRegistry()
    registry.register(IntentCategory.CLAIMS, ClaimsAgent())
    registry.register(IntentCategory.BROKER, BrokerAgent())
    registry.register(IntentCategory.COMMERCIAL, CommercialIntakeAgent())
    registry.register(IntentCategory.UNKNOWN, FallbackAgent())

    return SupervisorOrchestrator(
        conversation_repository=repository,
        intent_resolver=RuleBasedIntentResolver(),
        agent_registry=registry,
    )

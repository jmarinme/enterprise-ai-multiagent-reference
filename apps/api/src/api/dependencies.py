"""FastAPI dependency-injection wiring for the Supervisor orchestration framework and the
Tool execution framework.

This is the composition root: it is the one place that imports concrete Agent classes and
concrete Tool classes and wires them into their respective registries. src/supervisor/ and
src/tools/ never import any concrete agent or tool — adding a new agent or tool means adding
lines here, not touching either framework.
"""

from __future__ import annotations

from functools import lru_cache

from src.agents.broker_agent import BrokerAgent
from src.agents.claims_agent import ClaimsAgent
from src.agents.commercial_intake_agent import CommercialIntakeAgent
from src.agents.fallback_agent import FallbackAgent
from src.services.conversation_store.factory import get_conversation_repository
from src.services.tools.broker_account_lookup_tool import BrokerAccountLookupTool
from src.services.tools.claims_status_tool import ClaimsStatusTool
from src.services.tools.policy_lookup_tool import PolicyLookupTool
from src.supervisor.intent import RuleBasedIntentResolver
from src.supervisor.models import IntentCategory
from src.supervisor.orchestrator import SupervisorOrchestrator
from src.supervisor.registry import InMemoryAgentRegistry
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry

from src.config.settings import ConversationStoreSettings


@lru_cache
def get_tool_executor() -> ToolExecutor:
    """Build and cache the process-wide ToolExecutor, with every synthetic Tool registered.

    This is the only place any concrete Tool is imported or registered — Agents depend on
    ToolExecutor alone.
    """
    tool_registry = InMemoryToolRegistry()
    tool_registry.register(PolicyLookupTool())
    tool_registry.register(ClaimsStatusTool())
    tool_registry.register(BrokerAccountLookupTool())
    return ToolExecutor(tool_registry=tool_registry)


@lru_cache
def get_supervisor() -> SupervisorOrchestrator:
    """Build and cache the process-wide Supervisor instance."""
    conversation_store_settings = ConversationStoreSettings()
    repository = get_conversation_repository(conversation_store_settings)
    tool_executor = get_tool_executor()

    registry = InMemoryAgentRegistry()
    registry.register(IntentCategory.CLAIMS, ClaimsAgent(tool_executor=tool_executor))
    registry.register(IntentCategory.BROKER, BrokerAgent())
    registry.register(IntentCategory.COMMERCIAL, CommercialIntakeAgent())
    registry.register(IntentCategory.UNKNOWN, FallbackAgent())

    return SupervisorOrchestrator(
        conversation_repository=repository,
        intent_resolver=RuleBasedIntentResolver(),
        agent_registry=registry,
    )

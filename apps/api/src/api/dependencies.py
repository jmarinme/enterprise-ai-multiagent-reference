"""FastAPI dependency-injection wiring for the Supervisor orchestration framework, the Tool
execution framework, and the Prompt Management framework.

This is the composition root: it is the one place that imports concrete Agent classes, Tool
classes, and PromptProvider classes and wires them into their respective
registries/managers. src/supervisor/, src/tools/, and src/prompts/ never import any concrete
agent, tool, or prompt provider — adding a new one means adding lines here, not touching any
framework.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from src.agents.broker_agent import BrokerAgent
from src.agents.claims_agent import ClaimsAgent
from src.agents.commercial_intake_agent import CommercialIntakeAgent
from src.agents.fallback_agent import FallbackAgent
from src.prompts.filesystem_provider import FileSystemPromptProvider
from src.prompts.manager import PromptManager
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

# Relative to the process's working directory (repo root locally, /app in the Docker image —
# see apps/api/Dockerfile), matching how the existing .env file is already resolved.
_PROMPTS_ROOT = Path("configs/prompts")


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
def get_prompt_manager() -> PromptManager:
    """Build and cache the process-wide PromptManager, backed by the local
    FileSystemPromptProvider.

    This is the only place any concrete PromptProvider is chosen — Agents depend on
    PromptManager alone. Swapping in a future Azure-backed provider means changing this one
    function, not any Agent.
    """
    provider = FileSystemPromptProvider(prompts_root=_PROMPTS_ROOT)
    return PromptManager(provider=provider)


@lru_cache
def get_supervisor() -> SupervisorOrchestrator:
    """Build and cache the process-wide Supervisor instance."""
    conversation_store_settings = ConversationStoreSettings()
    repository = get_conversation_repository(conversation_store_settings)
    tool_executor = get_tool_executor()
    prompt_manager = get_prompt_manager()

    registry = InMemoryAgentRegistry()
    registry.register(
        IntentCategory.CLAIMS,
        ClaimsAgent(tool_executor=tool_executor, prompt_manager=prompt_manager),
    )
    registry.register(IntentCategory.BROKER, BrokerAgent())
    registry.register(IntentCategory.COMMERCIAL, CommercialIntakeAgent())
    registry.register(IntentCategory.UNKNOWN, FallbackAgent())

    return SupervisorOrchestrator(
        conversation_repository=repository,
        intent_resolver=RuleBasedIntentResolver(),
        agent_registry=registry,
    )

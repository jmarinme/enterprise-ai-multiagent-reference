"""FastAPI dependency-injection wiring for the Supervisor orchestration framework, the Tool
execution framework, the Prompt Management framework, and the LLM Adapter framework.

This is the composition root: it is the one place that imports concrete Agent classes, Tool
classes, PromptProvider classes, and LLMProvider classes and wires them into their respective
registries/managers. src/supervisor/, src/tools/, src/prompts/, and src/llm/ never import any
concrete agent, tool, prompt provider, or LLM provider — adding a new one means adding lines
here, not touching any framework.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from src.agents.broker_agent import BrokerAgent
from src.agents.claims_agent import ClaimsAgent
from src.agents.commercial_intake_agent import CommercialIntakeAgent
from src.agents.fallback_agent import FallbackAgent
from src.core.tool_calling.orchestrator import ToolCallingOrchestrator
from src.domain.conversation_repository import ConversationRepository
from src.domain.secret_provider import SecretProvider
from src.llm.factory import get_llm_provider as build_llm_provider
from src.llm.provider import LLMProvider
from src.prompts.filesystem_provider import FileSystemPromptProvider
from src.prompts.manager import PromptManager
from src.rag.factory import get_knowledge_provider as build_knowledge_provider
from src.rag.grounder import Grounder
from src.rag.retriever import KnowledgeRetriever
from src.services.conversation_store.factory import get_conversation_repository
from src.services.secret_store.factory import get_secret_provider as build_secret_provider
from src.services.tools.adjuster_assignment_tool import AdjusterAssignmentTool
from src.services.tools.broker_account_lookup_tool import BrokerAccountLookupTool
from src.services.tools.claim_registration_tool import ClaimRegistrationTool
from src.services.tools.claims_status_tool import ClaimsStatusTool
from src.services.tools.commission_lookup_tool import CommissionLookupTool
from src.services.tools.commission_payment_request_tool import CommissionPaymentRequestTool
from src.services.tools.coverage_lookup_tool import CoverageLookupTool
from src.services.tools.customer_lookup_tool import CustomerLookupTool
from src.services.tools.lead_registration_tool import LeadRegistrationTool
from src.services.tools.payment_status_tool import PaymentStatusTool
from src.services.tools.policy_lookup_tool import PolicyLookupTool
from src.services.tools.transaction_status_tool import TransactionStatusTool
from src.supervisor.intent import RuleBasedIntentResolver
from src.supervisor.models import IntentCategory
from src.supervisor.orchestrator import SupervisorOrchestrator
from src.supervisor.registry import InMemoryAgentRegistry
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry, ToolRegistry

from src.config.settings import (
    ConversationStoreSettings,
    KnowledgeSettings,
    LLMSettings,
    SecretProviderSettings,
    ToolCallingSettings,
)

# Relative to the process's working directory (repo root locally, /app in the Docker image —
# see apps/api/Dockerfile), matching how the existing .env file is already resolved.
_PROMPTS_ROOT = Path("configs/prompts")
_KNOWLEDGE_BASE_ROOT = Path("configs/knowledge_base")


@lru_cache
def get_tool_registry() -> ToolRegistry:
    """Build and cache the process-wide ToolRegistry, with every synthetic Tool registered.

    This is the only place any concrete Tool is imported or registered. Exposed separately from
    get_tool_executor() (PBI-02-04) so ToolCallingOrchestrator can build LLM tool definitions
    from the exact same registered Tools ToolExecutor executes against — reusing, never
    recreating, the registry (CLAUDE.md §7).
    """
    tool_registry = InMemoryToolRegistry()
    tool_registry.register(PolicyLookupTool())
    tool_registry.register(ClaimsStatusTool())
    tool_registry.register(BrokerAccountLookupTool())
    tool_registry.register(PaymentStatusTool())
    tool_registry.register(ClaimRegistrationTool())
    tool_registry.register(AdjusterAssignmentTool())
    tool_registry.register(TransactionStatusTool())
    tool_registry.register(CommissionLookupTool())
    tool_registry.register(CommissionPaymentRequestTool())
    tool_registry.register(LeadRegistrationTool())
    tool_registry.register(CustomerLookupTool())
    tool_registry.register(CoverageLookupTool())
    return tool_registry


@lru_cache
def get_tool_executor() -> ToolExecutor:
    """Build and cache the process-wide ToolExecutor. Agents depend on ToolExecutor alone —
    never on ToolRegistry directly."""
    return ToolExecutor(tool_registry=get_tool_registry())


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
def get_knowledge_retriever() -> KnowledgeRetriever:
    """Build and cache the process-wide KnowledgeRetriever.

    Local by default (KNOWLEDGE_PROVIDER=local) — no Azure connectivity required locally or in
    tests. This is the only place any concrete KnowledgeProvider (local or Azure AI Search) is
    chosen — Agents depend on KnowledgeRetriever alone. Swapping providers means changing this
    one function, not any Agent.
    """
    knowledge_settings = KnowledgeSettings()
    secret_provider: SecretProvider | None = None
    if knowledge_settings.azure_ai_search_use_api_key:
        secret_provider = build_secret_provider(SecretProviderSettings())
    provider = build_knowledge_provider(
        knowledge_settings,
        local_documents_root=_KNOWLEDGE_BASE_ROOT,
        secret_provider=secret_provider,
    )
    return KnowledgeRetriever(provider=provider)


@lru_cache
def get_grounder() -> Grounder:
    """Build and cache the process-wide Grounder (PBI-02-03).

    Stateless — this factory exists only to keep the composition-root pattern uniform, matching
    every other framework dependency Agents receive via constructor injection.
    """
    return Grounder()


@lru_cache
def get_llm_provider() -> LLMProvider:
    """Build and cache the process-wide LLMProvider.

    Mock by default (LLM_PROVIDER=mock) — no Azure connectivity required locally or in tests.
    This is the only place any concrete LLMProvider (Mock or Azure OpenAI) is chosen — Agents
    depend on LLMProvider alone. Swapping providers, or adding a third one later, means
    changing this one function, not any Agent.
    """
    llm_settings = LLMSettings()
    secret_provider: SecretProvider | None = None
    if llm_settings.azure_openai_use_api_key:
        secret_provider = build_secret_provider(SecretProviderSettings())
    return build_llm_provider(llm_settings, secret_provider=secret_provider)


@lru_cache
def get_tool_calling_orchestrator() -> ToolCallingOrchestrator:
    """Build and cache the process-wide ToolCallingOrchestrator (PBI-02-04).

    Reuses the same cached ToolRegistry/ToolExecutor/LLMProvider instances every other
    framework dependency already uses — never a second, competing registry or executor.
    max_iterations is not read here: it is per-call, supplied by each Agent via
    ToolCallingContext (see src.core.tool_calling.models.DEFAULT_MAX_TOOL_CALL_ITERATIONS and
    ToolCallingSettings.tool_calling_max_iterations for where an Agent should source it).
    """
    return ToolCallingOrchestrator(
        tool_registry=get_tool_registry(),
        tool_executor=get_tool_executor(),
        llm_provider=get_llm_provider(),
    )


@lru_cache
def get_conversation_repository_dep() -> ConversationRepository:
    """Build and cache the process-wide ConversationRepository (PBI-04-04's conversation-
    history endpoints reuse this exact instance — never a second, competing repository).
    """
    return get_conversation_repository(ConversationStoreSettings())


@lru_cache
def get_supervisor() -> SupervisorOrchestrator:
    """Build and cache the process-wide Supervisor instance.

    Reuses get_conversation_repository_dep()'s exact cached instance (PBI-04-04) — not a
    second, independently-constructed repository — so a conversation POST /chat just wrote is
    always visible to GET /conversations in the same process, including the in-memory adapter
    used locally/in tests, which holds state only in its own instance's dict.
    """
    repository = get_conversation_repository_dep()
    tool_executor = get_tool_executor()
    prompt_manager = get_prompt_manager()
    llm_provider = get_llm_provider()
    knowledge_retriever = get_knowledge_retriever()
    grounder = get_grounder()
    tool_calling_orchestrator = get_tool_calling_orchestrator()
    tool_calling_settings = ToolCallingSettings()

    registry = InMemoryAgentRegistry()
    registry.register(
        IntentCategory.CLAIMS,
        ClaimsAgent(
            tool_executor=tool_executor,
            prompt_manager=prompt_manager,
            llm_provider=llm_provider,
            knowledge_retriever=knowledge_retriever,
            grounder=grounder,
            tool_calling_orchestrator=tool_calling_orchestrator,
            tool_calling_max_iterations=tool_calling_settings.tool_calling_max_iterations,
        ),
    )
    registry.register(
        IntentCategory.BROKER,
        BrokerAgent(
            tool_executor=tool_executor,
            prompt_manager=prompt_manager,
            llm_provider=llm_provider,
        ),
    )
    registry.register(
        IntentCategory.COMMERCIAL,
        CommercialIntakeAgent(
            tool_executor=tool_executor,
            prompt_manager=prompt_manager,
            llm_provider=llm_provider,
        ),
    )
    registry.register(IntentCategory.UNKNOWN, FallbackAgent())

    return SupervisorOrchestrator(
        conversation_repository=repository,
        intent_resolver=RuleBasedIntentResolver(),
        agent_registry=registry,
    )

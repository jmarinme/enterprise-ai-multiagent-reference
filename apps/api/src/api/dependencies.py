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
from src.core.tool_provider.factory import get_tool_provider as build_tool_provider
from src.core.tool_provider.protocol import ToolProvider
from src.core.workflow_provider.factory import (
    get_claims_workflow_provider as build_claims_workflow_provider,
)
from src.core.workflow_provider.protocol import ClaimsWorkflowProvider
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
from src.supervisor.models import IntentCategory
from src.supervisor.orchestrator import SupervisorOrchestrator
from src.supervisor.registry import InMemoryAgentRegistry
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry, ToolRegistry

from src.config.settings import (
    ClaimsWorkflowSettings,
    ConversationStoreSettings,
    KnowledgeSettings,
    LLMSettings,
    SecretProviderSettings,
    ToolCallingSettings,
    ToolProviderSettings,
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
    tool_registry.register(BrokerLookupTool())
    tool_registry.register(CommissionPeriodsLookupTool())
    return tool_registry


@lru_cache
def get_tool_executor() -> ToolExecutor:
    """Build and cache the process-wide ToolExecutor. Agents depend on ToolExecutor alone —
    never on ToolRegistry directly."""
    return ToolExecutor(tool_registry=get_tool_registry())


@lru_cache
def get_tool_provider() -> ToolProvider:
    """Build and cache the process-wide ToolProvider (PBI-06-01, resolves Architecture Review
    Finding A-03).

    In-process by default (TOOL_PROVIDER=inprocess) — wraps the exact same cached ToolExecutor/
    ToolRegistry every other framework dependency already uses, so behavior is unchanged unless
    TOOL_PROVIDER=azure_functions is explicitly configured. This is the only place any concrete
    ToolProvider backend is chosen — Agents depend on the ToolProvider abstraction alone.
    """
    tool_provider_settings = ToolProviderSettings()
    secret_provider: SecretProvider | None = None
    if tool_provider_settings.azure_functions_use_key:
        secret_provider = build_secret_provider(SecretProviderSettings())
    return build_tool_provider(
        tool_provider_settings, tool_executor=get_tool_executor(), secret_provider=secret_provider
    )


@lru_cache
def get_claims_workflow_provider() -> ClaimsWorkflowProvider:
    """Build and cache the process-wide ClaimsWorkflowProvider (PBI-06-01, resolves
    Architecture Review Finding A-03).

    In-process by default (CLAIMS_WORKFLOW_PROVIDER=inprocess) — reuses the same cached
    ToolProvider get_tool_provider() builds, so behavior is unchanged unless
    CLAIMS_WORKFLOW_PROVIDER=durable is explicitly configured. Only ClaimsAgent depends on
    this today (PBI-06-01 scope: Claims is the first fully migrated vertical slice; Broker and
    Commercial remain on their existing in-process implementation).
    """
    claims_workflow_settings = ClaimsWorkflowSettings()
    secret_provider: SecretProvider | None = None
    if claims_workflow_settings.durable_functions_use_key:
        secret_provider = build_secret_provider(SecretProviderSettings())
    return build_claims_workflow_provider(
        claims_workflow_settings,
        tool_provider=get_tool_provider(),
        secret_provider=secret_provider,
    )


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
            # PBI-06-01: Claims is the first fully migrated vertical slice — it depends on the
            # ToolProvider/ClaimsWorkflowProvider abstractions, not the concrete ToolExecutor
            # Broker/Commercial (below) still use directly. Both default to their in-process
            # backends, so behavior is unchanged unless TOOL_PROVIDER/CLAIMS_WORKFLOW_PROVIDER
            # are explicitly set.
            tool_executor=get_tool_provider(),
            prompt_manager=prompt_manager,
            llm_provider=llm_provider,
            knowledge_retriever=knowledge_retriever,
            grounder=grounder,
            tool_calling_orchestrator=tool_calling_orchestrator,
            tool_calling_max_iterations=tool_calling_settings.tool_calling_max_iterations,
            workflow_provider=get_claims_workflow_provider(),
        ),
    )
    registry.register(
        IntentCategory.BROKER,
        BrokerAgent(
            tool_executor=tool_executor,
            prompt_manager=prompt_manager,
            llm_provider=llm_provider,
            # PBI-12-04: reuses the exact same cached, process-wide ToolCallingOrchestrator
            # instance as ClaimsAgent — never a second, competing orchestrator.
            tool_calling_orchestrator=tool_calling_orchestrator,
            tool_calling_max_iterations=tool_calling_settings.tool_calling_max_iterations,
        ),
    )
    registry.register(
        IntentCategory.COMMERCIAL,
        CommercialIntakeAgent(
            tool_executor=tool_executor,
            prompt_manager=prompt_manager,
            llm_provider=llm_provider,
            # PBI-12-04: reuses the exact same cached, process-wide ToolCallingOrchestrator
            # instance as ClaimsAgent/BrokerAgent — never a second, competing orchestrator.
            tool_calling_orchestrator=tool_calling_orchestrator,
            tool_calling_max_iterations=tool_calling_settings.tool_calling_max_iterations,
        ),
    )
    registry.register(IntentCategory.UNKNOWN, FallbackAgent())

    return SupervisorOrchestrator(
        conversation_repository=repository,
        intent_resolver=RuleBasedIntentResolver(),
        agent_registry=registry,
    )

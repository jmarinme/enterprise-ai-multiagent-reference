"""Unit tests for the FastAPI composition root (apps/api/src/api/dependencies.py): Azure
runtime provider wiring (PBI-03-02) — provider selection, missing-configuration failures, and
the Managed Identity default auth path (no SecretProvider built unless *_USE_API_KEY is set).

Every get_*() function in dependencies.py is @lru_cache-decorated (process-wide singletons).
The autouse fixture below clears every cache before AND after each test in this file, so an
environment-variable-driven provider selection here can never leak a wrongly-configured
provider into any other test in the wider suite that assumes the Mock/local/in_memory defaults
(including this same file's own tests running in a different order).
"""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import patch

import pytest
from api import dependencies


def _clear_dependency_caches() -> None:
    dependencies.get_tool_registry.cache_clear()
    dependencies.get_tool_executor.cache_clear()
    dependencies.get_prompt_manager.cache_clear()
    dependencies.get_knowledge_retriever.cache_clear()
    dependencies.get_grounder.cache_clear()
    dependencies.get_llm_provider.cache_clear()
    dependencies.get_tool_calling_orchestrator.cache_clear()
    dependencies.get_conversation_repository_dep.cache_clear()
    dependencies.get_supervisor.cache_clear()


@pytest.fixture(autouse=True)
def _isolated_dependency_caches() -> Iterator[None]:
    _clear_dependency_caches()
    yield
    _clear_dependency_caches()


# --- LLM provider selection -------------------------------------------------------------------


def test_get_llm_provider_defaults_to_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.llm.mock_provider import MockLLMProvider

    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    provider = dependencies.get_llm_provider()

    assert isinstance(provider, MockLLMProvider)


def test_get_llm_provider_selects_azure_openai_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.llm.azure_openai_provider import AzureOpenAIProvider

    monkeypatch.setenv("LLM_PROVIDER", "azure_openai")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "chat")

    provider = dependencies.get_llm_provider()

    assert isinstance(provider, AzureOpenAIProvider)


def test_get_llm_provider_selects_ollama_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.llm.ollama_provider import OllamaLLMProvider

    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    provider = dependencies.get_llm_provider()

    assert isinstance(provider, OllamaLLMProvider)


def test_get_llm_provider_missing_azure_configuration_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.llm.exceptions import LLMConfigurationError

    monkeypatch.setenv("LLM_PROVIDER", "azure_openai")
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)

    with pytest.raises(LLMConfigurationError):
        dependencies.get_llm_provider()


def test_get_llm_provider_uses_managed_identity_by_default_not_secret_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Managed Identity path configuration (PBI-03-02): AZURE_OPENAI_USE_API_KEY defaults to
    false, so the composition root must never even build a SecretProvider — Managed Identity/
    DefaultAzureCredential handles auth entirely inside AzureOpenAIProvider itself."""
    monkeypatch.setenv("LLM_PROVIDER", "azure_openai")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "chat")
    monkeypatch.delenv("AZURE_OPENAI_USE_API_KEY", raising=False)

    with patch("api.dependencies.build_secret_provider") as mock_build_secret_provider:
        dependencies.get_llm_provider()

    mock_build_secret_provider.assert_not_called()


# --- Knowledge provider selection ---------------------------------------------------------------


def test_get_knowledge_retriever_defaults_to_local(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.rag.local_provider import LocalKnowledgeProvider

    monkeypatch.delenv("KNOWLEDGE_PROVIDER", raising=False)

    retriever = dependencies.get_knowledge_retriever()

    assert isinstance(retriever._provider, LocalKnowledgeProvider)


def test_get_knowledge_retriever_selects_azure_ai_search_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.rag.azure_ai_search_provider import AzureAISearchProvider

    monkeypatch.setenv("KNOWLEDGE_PROVIDER", "azure_ai_search")
    monkeypatch.setenv("AZURE_AI_SEARCH_ENDPOINT", "https://example.search.windows.net")
    monkeypatch.setenv("AZURE_AI_SEARCH_INDEX_NAME", "tmxap-knowledge-index")

    retriever = dependencies.get_knowledge_retriever()

    assert isinstance(retriever._provider, AzureAISearchProvider)


def test_get_knowledge_retriever_missing_azure_configuration_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.rag.exceptions import KnowledgeConfigurationError

    monkeypatch.setenv("KNOWLEDGE_PROVIDER", "azure_ai_search")
    monkeypatch.setenv("AZURE_AI_SEARCH_ENDPOINT", "https://example.search.windows.net")
    monkeypatch.delenv("AZURE_AI_SEARCH_INDEX_NAME", raising=False)

    with pytest.raises(KnowledgeConfigurationError):
        dependencies.get_knowledge_retriever()


def test_get_knowledge_retriever_uses_managed_identity_by_default_not_secret_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KNOWLEDGE_PROVIDER", "azure_ai_search")
    monkeypatch.setenv("AZURE_AI_SEARCH_ENDPOINT", "https://example.search.windows.net")
    monkeypatch.setenv("AZURE_AI_SEARCH_INDEX_NAME", "tmxap-knowledge-index")
    monkeypatch.delenv("AZURE_AI_SEARCH_USE_API_KEY", raising=False)

    with patch("api.dependencies.build_secret_provider") as mock_build_secret_provider:
        dependencies.get_knowledge_retriever()

    mock_build_secret_provider.assert_not_called()


# --- Conversation store (Cosmos) selection, via the full composition root ----------------------


def test_get_supervisor_defaults_to_in_memory_conversation_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.services.conversation_store.in_memory import InMemoryConversationRepository

    monkeypatch.delenv("CONVERSATION_STORE_PROVIDER", raising=False)

    supervisor = dependencies.get_supervisor()

    assert isinstance(supervisor._conversation_repository, InMemoryConversationRepository)


def test_get_supervisor_selects_cosmos_conversation_repository_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.services.conversation_store.cosmos import CosmosConversationRepository

    monkeypatch.setenv("CONVERSATION_STORE_PROVIDER", "cosmos")
    monkeypatch.setenv("COSMOS_DB_ENDPOINT", "https://example.documents.azure.com:443/")

    supervisor = dependencies.get_supervisor()

    assert isinstance(supervisor._conversation_repository, CosmosConversationRepository)


def test_get_supervisor_missing_cosmos_configuration_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CONVERSATION_STORE_PROVIDER", "cosmos")
    monkeypatch.delenv("COSMOS_DB_ENDPOINT", raising=False)

    with pytest.raises(ValueError, match="COSMOS_DB_ENDPOINT"):
        dependencies.get_supervisor()


# --- Full Azure-runtime composition -------------------------------------------------------------


def test_get_supervisor_wires_all_three_azure_providers_together(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Composition root wiring (PBI-03-02): with every Azure env var set at once (the shape
    Bicep's Container App now injects), get_supervisor() must build correctly without any
    Agent rewrite or extra wiring — proving the whole Azure runtime chain is genuinely
    configuration-driven end to end."""
    from src.llm.azure_openai_provider import AzureOpenAIProvider
    from src.rag.azure_ai_search_provider import AzureAISearchProvider
    from src.services.conversation_store.cosmos import CosmosConversationRepository

    monkeypatch.setenv("LLM_PROVIDER", "azure_openai")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "chat")
    monkeypatch.setenv("KNOWLEDGE_PROVIDER", "azure_ai_search")
    monkeypatch.setenv("AZURE_AI_SEARCH_ENDPOINT", "https://example.search.windows.net")
    monkeypatch.setenv("AZURE_AI_SEARCH_INDEX_NAME", "tmxap-knowledge-index")
    monkeypatch.setenv("CONVERSATION_STORE_PROVIDER", "cosmos")
    monkeypatch.setenv("COSMOS_DB_ENDPOINT", "https://example.documents.azure.com:443/")

    supervisor = dependencies.get_supervisor()

    claims_agent = supervisor._agent_registry.resolve(dependencies.IntentCategory.CLAIMS)
    assert isinstance(claims_agent._llm_provider, AzureOpenAIProvider)
    assert isinstance(claims_agent._knowledge_retriever._provider, AzureAISearchProvider)
    assert isinstance(supervisor._conversation_repository, CosmosConversationRepository)

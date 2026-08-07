"""Unit tests for get_knowledge_provider: provider selection."""

from pathlib import Path

from src.config.settings import KnowledgeSettings
from src.rag.factory import get_knowledge_provider
from src.rag.local_provider import LocalKnowledgeProvider

_LOCAL_ROOT = Path("configs/knowledge_base")


def test_factory_returns_local_provider_by_default() -> None:
    settings = KnowledgeSettings()

    provider = get_knowledge_provider(settings, local_documents_root=_LOCAL_ROOT)

    assert isinstance(provider, LocalKnowledgeProvider)


def test_factory_returns_azure_ai_search_provider_when_configured() -> None:
    from src.rag.azure_ai_search_provider import AzureAISearchProvider

    settings = KnowledgeSettings(
        knowledge_provider="azure_ai_search",
        azure_ai_search_endpoint="https://example.search.windows.net",
        azure_ai_search_index_name="knowledge-index",
    )

    provider = get_knowledge_provider(settings, local_documents_root=_LOCAL_ROOT)

    assert isinstance(provider, AzureAISearchProvider)


def test_factory_raises_for_unsupported_provider() -> None:
    settings = KnowledgeSettings.model_construct(knowledge_provider="unsupported")

    try:
        get_knowledge_provider(settings, local_documents_root=_LOCAL_ROOT)
    except ValueError as exc:
        assert "Unsupported knowledge provider" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported provider")

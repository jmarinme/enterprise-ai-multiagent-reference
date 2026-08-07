"""Selects a KnowledgeProvider implementation from configuration.

AzureAISearchProvider is imported lazily, inside the azure_ai_search branch, so the default
local provider never requires the azure-search-documents/azure-identity packages to be
installed or reachable — same pattern as src.llm.factory and
src.services.conversation_store.factory.

local_documents_root is accepted as a parameter (not hardcoded here) because a repo-relative
filesystem path is a composition-root concern (see apps/api/src/api/dependencies.py), not a
concern of this reusable domain-library factory.
"""

from __future__ import annotations

from pathlib import Path

from src.config.settings import KnowledgeSettings
from src.domain.secret_provider import SecretProvider
from src.rag.local_provider import LocalKnowledgeProvider
from src.rag.provider import KnowledgeProvider


def get_knowledge_provider(
    settings: KnowledgeSettings,
    local_documents_root: Path,
    secret_provider: SecretProvider | None = None,
) -> KnowledgeProvider:
    """Return the KnowledgeProvider implementation selected by settings."""
    if settings.knowledge_provider == "local":
        return LocalKnowledgeProvider(documents_root=local_documents_root)

    if settings.knowledge_provider == "azure_ai_search":
        from src.rag.azure_ai_search_provider import AzureAISearchProvider

        use_api_key = settings.azure_ai_search_use_api_key
        return AzureAISearchProvider(
            endpoint=settings.azure_ai_search_endpoint or "",
            index_name=settings.azure_ai_search_index_name or "",
            secret_provider=secret_provider if use_api_key else None,
            api_key_secret_name=(
                settings.azure_ai_search_api_key_secret_name if use_api_key else None
            ),
        )

    raise ValueError(f"Unsupported knowledge provider: {settings.knowledge_provider}")

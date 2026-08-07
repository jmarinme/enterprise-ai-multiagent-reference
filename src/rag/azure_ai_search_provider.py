"""AzureAISearchProvider: production-shaped Azure AI Search-backed KnowledgeProvider.

Prefers Microsoft Entra ID (DefaultAzureCredential) authentication, since the
azure-search-documents SDK's async SearchClient natively accepts an azure-identity credential.
API-key auth, if explicitly enabled via configuration, is obtained only through the existing
SecretProvider abstraction — never read directly from os.environ here. Structurally mirrors
src.llm.azure_openai_provider.AzureOpenAIProvider (PBI-01-04) exactly.

Never exercised by the test suite against real Azure — LocalKnowledgeProvider is the default
and only provider the tests actually call (see src/rag/factory.py). This file is the only
place in the codebase that imports the azure-search-documents SDK.

Plain keyword search only (search_text=), matching CLAUDE.md §4.4's documentary-RAG scope and
this PBI's explicit exclusions: no vector query (KnowledgeQuery/KnowledgeChunk have no
embedding fields, so vector search is not required by the existing contract) and no semantic
ranker (not justified — this is a small synthetic reference corpus).

Assumed index schema (index creation/ingestion is a future PBI's concern, explicitly out of
scope here): a key field "chunk_id", a searchable "content" field, and "source_id"/"title"/
"category" fields matching KnowledgeMetadata's own field names.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from azure.core.exceptions import (
    ClientAuthenticationError,
    HttpResponseError,
    ServiceRequestError,
)
from azure.search.documents.aio import SearchClient

from src.domain.secret_provider import SecretProvider
from src.rag.exceptions import (
    KnowledgeConfigurationError,
    KnowledgeProviderError,
    KnowledgeTimeoutError,
)
from src.rag.models import KnowledgeChunk, KnowledgeMetadata, KnowledgeQuery, KnowledgeResult

_PROVIDER_NAME = "azure_ai_search"
_ENTRA_ID_SCOPE = "https://search.azure.com/.default"
_SELECT_FIELDS: Sequence[str] = ("chunk_id", "content", "source_id", "title", "category")


class AzureAISearchProvider:
    """KnowledgeProvider implementation backed by Azure AI Search."""

    def __init__(
        self,
        endpoint: str,
        index_name: str,
        secret_provider: SecretProvider | None = None,
        api_key_secret_name: str | None = None,
    ) -> None:
        if not endpoint:
            raise KnowledgeConfigurationError(
                "AZURE_AI_SEARCH_ENDPOINT must be set for the azure_ai_search provider"
            )
        if not index_name:
            raise KnowledgeConfigurationError(
                "AZURE_AI_SEARCH_INDEX_NAME must be set for the azure_ai_search provider"
            )

        self._endpoint = endpoint
        self._index_name = index_name
        self._secret_provider = secret_provider
        self._api_key_secret_name = api_key_secret_name
        self._client: SearchClient | None = None
        self._credential_close: object | None = None

    async def _get_client(self) -> SearchClient:
        if self._client is not None:
            return self._client

        if self._secret_provider is not None and self._api_key_secret_name:
            from azure.core.credentials import AzureKeyCredential

            api_key = await self._secret_provider.get_secret(self._api_key_secret_name)
            self._client = SearchClient(
                endpoint=self._endpoint,
                index_name=self._index_name,
                credential=AzureKeyCredential(api_key),
            )
        else:
            from azure.identity.aio import DefaultAzureCredential

            credential = DefaultAzureCredential()
            self._credential_close = credential
            self._client = SearchClient(
                endpoint=self._endpoint,
                index_name=self._index_name,
                credential=credential,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
        if self._credential_close is not None:
            await self._credential_close.close()  # type: ignore[attr-defined]

    async def retrieve(self, query: KnowledgeQuery) -> KnowledgeResult:
        client = await self._get_client()
        filter_expression = f"category eq '{query.category}'" if query.category else None

        try:
            pages = await client.search(
                search_text=query.text,
                top=query.top_k,
                filter=filter_expression,
                select=list(_SELECT_FIELDS),
            )
            chunks = [self._to_chunk(item) async for item in pages]
        except ClientAuthenticationError as exc:
            raise KnowledgeProviderError(_PROVIDER_NAME, f"authentication failed: {exc}") from exc
        except ServiceRequestError as exc:
            raise KnowledgeTimeoutError(_PROVIDER_NAME, str(exc)) from exc
        except HttpResponseError as exc:
            raise KnowledgeProviderError(_PROVIDER_NAME, str(exc)) from exc

        return KnowledgeResult(query=query, chunks=chunks)

    @staticmethod
    def _to_chunk(item: dict[str, Any]) -> KnowledgeChunk:
        return KnowledgeChunk(
            chunk_id=item["chunk_id"],
            text=item["content"],
            metadata=KnowledgeMetadata(
                source_id=item["source_id"],
                title=item["title"],
                category=item["category"],
            ),
            score=item.get("@search.score", 0.0),
        )

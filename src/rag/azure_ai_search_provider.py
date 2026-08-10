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

Index schema (PBI-03-03: src.pipelines.knowledge_ingestion.index_schema.build_index_definition
is now the authoritative definition, created/updated by the ingestion pipeline, not this
provider): a key field "chunk_id", a searchable "content" field, and "source_id"/"title"/
"category"/"section"/"source_path" fields matching KnowledgeMetadata's own field names.
"section"/"source_path" are still read via .get() rather than asserted required — an index
predating PBI-03-03's ingestion pipeline (or a document ingested without a section) simply
leaves them None, which still produces a valid KnowledgeChunk.
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

from src.core.resilience import CircuitBreaker, CircuitBreakerOpenError, retry_with_backoff
from src.domain.secret_provider import SecretProvider
from src.rag.exceptions import (
    KnowledgeConfigurationError,
    KnowledgeProviderError,
    KnowledgeTimeoutError,
)
from src.rag.models import KnowledgeChunk, KnowledgeMetadata, KnowledgeQuery, KnowledgeResult

_PROVIDER_NAME = "azure_ai_search"
_ENTRA_ID_SCOPE = "https://search.azure.com/.default"
# Extended to include "section"/"source_path" (PBI-03-03): the ingestion pipeline's index
# schema (src.pipelines.knowledge_ingestion.index_schema.build_index_definition) now defines
# both fields, so requesting them in `select` no longer risks Azure AI Search's 400 "unknown
# field" error the way it would have against the pre-PBI-03-03 assumed minimal schema.
_SELECT_FIELDS: Sequence[str] = (
    "chunk_id",
    "content",
    "source_id",
    "title",
    "category",
    "section",
    "source_path",
)

# Resilience (Architecture Review Finding A-07, CLAUDE.md principle #9): ServiceRequestError is
# a genuine transport-level failure (DNS, connection refused, connection reset) — retryable.
# ClientAuthenticationError (bad credential/config) and the generic HttpResponseError (covers
# both retryable 5xx and non-retryable 4xx without a distinguishing exception type) are
# deliberately NOT retried here, matching the same conservative approach
# src.llm.azure_openai_provider takes for its own ambiguous status-error case.
_RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (ServiceRequestError,)
_RETRY_MAX_ATTEMPTS = 3
_RETRY_BASE_DELAY_SECONDS = 0.5
_RETRY_MAX_DELAY_SECONDS = 8.0
_CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
_CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS = 30.0


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
        self._circuit_breaker = CircuitBreaker(
            _PROVIDER_NAME,
            failure_threshold=_CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            reset_timeout_seconds=_CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS,
        )

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

        async def _search_and_collect() -> list[KnowledgeChunk]:
            pages = await client.search(
                search_text=query.text,
                top=query.top_k,
                filter=filter_expression,
                select=list(_SELECT_FIELDS),
            )
            return [self._to_chunk(item) async for item in pages]

        async def _resilient_search() -> list[KnowledgeChunk]:
            return await retry_with_backoff(
                _search_and_collect,
                retryable_exceptions=_RETRYABLE_EXCEPTIONS,
                max_attempts=_RETRY_MAX_ATTEMPTS,
                base_delay_seconds=_RETRY_BASE_DELAY_SECONDS,
                max_delay_seconds=_RETRY_MAX_DELAY_SECONDS,
                operation_name=f"{_PROVIDER_NAME} search",
            )

        try:
            chunks = await self._circuit_breaker.call(_resilient_search)
        except CircuitBreakerOpenError as exc:
            raise KnowledgeProviderError(_PROVIDER_NAME, str(exc)) from exc
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
                # .get(), not item[...]: a document ingested without a section (e.g. a
                # short, unsectioned Markdown file — see MarkdownDocumentLoader) legitimately
                # has this field absent/None, which is a valid, expected value, not an error.
                section=item.get("section"),
                source_path=item.get("source_path"),
            ),
            score=item.get("@search.score", 0.0),
        )

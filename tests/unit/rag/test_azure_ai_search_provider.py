"""Unit tests for AzureAISearchProvider, fully mocked — no real Azure connectivity anywhere.

Covers: configuration validation, mocked successful search, no results, top-k, category
filtering, metadata mapping for citations, mocked authentication/timeout/generic provider
errors, and the Entra ID vs. SecretProvider-backed API-key auth paths.
"""

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from azure.core.exceptions import (
    ClientAuthenticationError,
    HttpResponseError,
    ServiceRequestError,
)

from src.rag.exceptions import (
    KnowledgeConfigurationError,
    KnowledgeProviderError,
    KnowledgeTimeoutError,
)
from src.rag.models import KnowledgeQuery

if TYPE_CHECKING:
    from src.rag.azure_ai_search_provider import AzureAISearchProvider


async def _async_iter(items: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    for item in items:
        yield item


def _fake_item(
    chunk_id: str = "KB-TEST-0001",
    content: str = "some retrieved text",
    source_id: str = "KB-TEST-0001",
    title: str = "Test Document",
    category: str = "claims_procedures",
    score: float = 1.5,
) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "content": content,
        "source_id": source_id,
        "title": title,
        "category": category,
        "@search.score": score,
    }


def test_missing_endpoint_raises_configuration_error() -> None:
    from src.rag.azure_ai_search_provider import AzureAISearchProvider

    with pytest.raises(KnowledgeConfigurationError):
        AzureAISearchProvider(endpoint="", index_name="knowledge-index")


def test_missing_index_name_raises_configuration_error() -> None:
    from src.rag.azure_ai_search_provider import AzureAISearchProvider

    with pytest.raises(KnowledgeConfigurationError):
        AzureAISearchProvider(endpoint="https://example.search.windows.net", index_name="")


def _build_provider() -> "AzureAISearchProvider":
    from src.rag.azure_ai_search_provider import AzureAISearchProvider

    return AzureAISearchProvider(
        endpoint="https://example.search.windows.net",
        index_name="knowledge-index",
    )


@patch("src.rag.azure_ai_search_provider.SearchClient")
@patch("azure.identity.aio.DefaultAzureCredential")
async def test_retrieve_success_returns_typed_chunks(
    mock_credential_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    mock_client = mock_client_cls.return_value
    mock_client.search = AsyncMock(return_value=_async_iter([_fake_item()]))
    provider = _build_provider()

    result = await provider.retrieve(KnowledgeQuery(text="claim procedure"))

    assert len(result.chunks) == 1
    chunk = result.chunks[0]
    assert chunk.chunk_id == "KB-TEST-0001"
    assert chunk.text == "some retrieved text"
    assert chunk.score == 1.5


@patch("src.rag.azure_ai_search_provider.SearchClient")
@patch("azure.identity.aio.DefaultAzureCredential")
async def test_retrieve_maps_metadata_for_future_citations(
    mock_credential_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    mock_client = mock_client_cls.return_value
    mock_client.search = AsyncMock(
        return_value=_async_iter(
            [_fake_item(source_id="KB-CLAIMS-0001", title="After Hours", category="claims_procedures")]
        )
    )
    provider = _build_provider()

    result = await provider.retrieve(KnowledgeQuery(text="claim procedure"))

    metadata = result.chunks[0].metadata
    assert metadata.source_id == "KB-CLAIMS-0001"
    assert metadata.title == "After Hours"
    assert metadata.category == "claims_procedures"


@patch("src.rag.azure_ai_search_provider.SearchClient")
@patch("azure.identity.aio.DefaultAzureCredential")
async def test_retrieve_with_no_matches_returns_an_explicit_empty_result(
    mock_credential_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    mock_client = mock_client_cls.return_value
    mock_client.search = AsyncMock(return_value=_async_iter([]))
    provider = _build_provider()

    result = await provider.retrieve(KnowledgeQuery(text="unmatched query"))

    assert result.chunks == []
    assert result.has_results is False


@patch("src.rag.azure_ai_search_provider.SearchClient")
@patch("azure.identity.aio.DefaultAzureCredential")
async def test_retrieve_passes_top_k_through_to_the_search_call(
    mock_credential_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    mock_client = mock_client_cls.return_value
    mock_client.search = AsyncMock(return_value=_async_iter([]))
    provider = _build_provider()

    await provider.retrieve(KnowledgeQuery(text="claim procedure", top_k=7))

    _, search_kwargs = mock_client.search.call_args
    assert search_kwargs["top"] == 7


@patch("src.rag.azure_ai_search_provider.SearchClient")
@patch("azure.identity.aio.DefaultAzureCredential")
async def test_retrieve_passes_a_category_filter_when_provided(
    mock_credential_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    mock_client = mock_client_cls.return_value
    mock_client.search = AsyncMock(return_value=_async_iter([]))
    provider = _build_provider()

    await provider.retrieve(KnowledgeQuery(text="claim procedure", category="claims_procedures"))

    _, search_kwargs = mock_client.search.call_args
    assert search_kwargs["filter"] == "category eq 'claims_procedures'"


@patch("src.rag.azure_ai_search_provider.SearchClient")
@patch("azure.identity.aio.DefaultAzureCredential")
async def test_retrieve_omits_the_filter_when_no_category_is_given(
    mock_credential_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    mock_client = mock_client_cls.return_value
    mock_client.search = AsyncMock(return_value=_async_iter([]))
    provider = _build_provider()

    await provider.retrieve(KnowledgeQuery(text="claim procedure"))

    _, search_kwargs = mock_client.search.call_args
    assert search_kwargs["filter"] is None


@patch("src.rag.azure_ai_search_provider.SearchClient")
@patch("azure.identity.aio.DefaultAzureCredential")
async def test_authentication_failure_raises_knowledge_provider_error(
    mock_credential_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    mock_client = mock_client_cls.return_value
    mock_client.search = AsyncMock(side_effect=ClientAuthenticationError("bad credentials"))
    provider = _build_provider()

    with pytest.raises(KnowledgeProviderError):
        await provider.retrieve(KnowledgeQuery(text="claim procedure"))


@patch("src.rag.azure_ai_search_provider.SearchClient")
@patch("azure.identity.aio.DefaultAzureCredential")
async def test_service_request_error_raises_knowledge_timeout_error(
    mock_credential_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    mock_client = mock_client_cls.return_value
    mock_client.search = AsyncMock(side_effect=ServiceRequestError("connection timed out"))
    provider = _build_provider()

    with pytest.raises(KnowledgeTimeoutError):
        await provider.retrieve(KnowledgeQuery(text="claim procedure"))


@patch("src.rag.azure_ai_search_provider.SearchClient")
@patch("azure.identity.aio.DefaultAzureCredential")
async def test_generic_http_response_error_raises_knowledge_provider_error(
    mock_credential_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    mock_client = mock_client_cls.return_value
    mock_client.search = AsyncMock(side_effect=HttpResponseError("internal server error"))
    provider = _build_provider()

    with pytest.raises(KnowledgeProviderError):
        await provider.retrieve(KnowledgeQuery(text="claim procedure"))


@patch("src.rag.azure_ai_search_provider.SearchClient")
@patch("azure.identity.aio.DefaultAzureCredential")
async def test_default_auth_uses_entra_id_not_secret_provider(
    mock_credential_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    mock_client_cls.return_value.search = AsyncMock(return_value=_async_iter([]))
    provider = _build_provider()

    await provider.retrieve(KnowledgeQuery(text="claim procedure"))

    mock_credential_cls.assert_called_once()
    _, client_kwargs = mock_client_cls.call_args
    assert "credential" in client_kwargs
    assert client_kwargs["credential"] is mock_credential_cls.return_value


@patch("src.rag.azure_ai_search_provider.SearchClient")
async def test_api_key_auth_uses_secret_provider_not_environment(mock_client_cls: MagicMock) -> None:
    from src.rag.azure_ai_search_provider import AzureAISearchProvider

    class _StubSecretProvider:
        async def get_secret(self, secret_name: str) -> str:
            assert secret_name == "azure-ai-search-api-key"
            return "mock-secret-value-not-a-real-key"

    mock_client_cls.return_value.search = AsyncMock(return_value=_async_iter([]))
    provider = AzureAISearchProvider(
        endpoint="https://example.search.windows.net",
        index_name="knowledge-index",
        secret_provider=_StubSecretProvider(),
        api_key_secret_name="azure-ai-search-api-key",
    )

    await provider.retrieve(KnowledgeQuery(text="claim procedure"))

    _, client_kwargs = mock_client_cls.call_args
    credential = client_kwargs["credential"]
    assert credential.key == "mock-secret-value-not-a-real-key"

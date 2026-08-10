"""Unit tests for CosmosConversationRepository's resilience wrapping (Architecture Review
Finding A-07) — fully mocked, no real Cosmos DB connectivity anywhere. Complements
tests/integration/test_cosmos_conversation_repository.py (a real-Cosmos, skipped-by-default
scaffold that never exercises retry/circuit-breaker behavior since it only runs against a
healthy live endpoint).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from azure.core.exceptions import ServiceRequestError
from azure.cosmos import exceptions

from src.domain.conversation import Conversation


async def _async_iter(items: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    for item in items:
        yield item


def _build_repo(mock_client_cls: MagicMock) -> tuple[Any, MagicMock]:
    from src.services.conversation_store.cosmos import CosmosConversationRepository

    mock_container = MagicMock()
    mock_client_cls.return_value.get_database_client.return_value.get_container_client.return_value = (
        mock_container
    )
    repo = CosmosConversationRepository(
        endpoint="https://example.documents.azure.com:443/",
        database_name="test-db",
        container_name="conversations",
    )
    return repo, mock_container


@patch("src.services.conversation_store.cosmos.CosmosClient")
@patch("azure.identity.aio.DefaultAzureCredential")
async def test_create_conversation_retries_a_transient_service_error_then_succeeds(
    mock_credential_cls: MagicMock, mock_client_cls: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    import src.services.conversation_store.cosmos as module

    monkeypatch.setattr(module, "_RETRY_BASE_DELAY_SECONDS", 0.001)
    monkeypatch.setattr(module, "_RETRY_MAX_DELAY_SECONDS", 0.002)

    repo, container = _build_repo(mock_client_cls)
    conversation = Conversation(user_id="user-1")
    stored_item = conversation.model_dump(mode="json", by_alias=True)
    container.create_item = AsyncMock(
        side_effect=[ServiceRequestError("connection reset"), stored_item]
    )

    result = await repo.create_conversation(conversation)

    assert result.id == conversation.id
    assert container.create_item.await_count == 2


@patch("src.services.conversation_store.cosmos.CosmosClient")
@patch("azure.identity.aio.DefaultAzureCredential")
async def test_get_conversation_not_found_returns_none_without_retrying(
    mock_credential_cls: MagicMock, mock_client_cls: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A 404 is a real, expected outcome (no such conversation) — it must propagate to the
    existing not-found handler on the FIRST attempt, never be retried."""
    import src.services.conversation_store.cosmos as module

    monkeypatch.setattr(module, "_RETRY_BASE_DELAY_SECONDS", 0.001)

    repo, container = _build_repo(mock_client_cls)
    container.read_item = AsyncMock(
        side_effect=exceptions.CosmosResourceNotFoundError(status_code=404, message="not found")
    )

    result = await repo.get_conversation("user-1", "missing-conversation")

    assert result is None
    assert container.read_item.await_count == 1


@patch("src.services.conversation_store.cosmos.CosmosClient")
@patch("azure.identity.aio.DefaultAzureCredential")
async def test_get_conversation_retries_a_throttled_429_then_succeeds(
    mock_credential_cls: MagicMock, mock_client_cls: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    import src.services.conversation_store.cosmos as module

    monkeypatch.setattr(module, "_RETRY_BASE_DELAY_SECONDS", 0.001)
    monkeypatch.setattr(module, "_RETRY_MAX_DELAY_SECONDS", 0.002)

    repo, container = _build_repo(mock_client_cls)
    conversation = Conversation(user_id="user-1")
    stored_item = conversation.model_dump(mode="json", by_alias=True)
    container.read_item = AsyncMock(
        side_effect=[
            exceptions.CosmosHttpResponseError(status_code=429, message="request rate too large"),
            stored_item,
        ]
    )

    result = await repo.get_conversation("user-1", conversation.id)

    assert result is not None
    assert result.id == conversation.id
    assert container.read_item.await_count == 2


@patch("src.services.conversation_store.cosmos.CosmosClient")
@patch("azure.identity.aio.DefaultAzureCredential")
async def test_create_conversation_does_not_retry_a_conflict(
    mock_credential_cls: MagicMock, mock_client_cls: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A 409 (already exists) is a real, non-transient business outcome — never retried."""
    import src.services.conversation_store.cosmos as module

    monkeypatch.setattr(module, "_RETRY_BASE_DELAY_SECONDS", 0.001)

    repo, container = _build_repo(mock_client_cls)
    conversation = Conversation(user_id="user-1")
    container.create_item = AsyncMock(
        side_effect=exceptions.CosmosResourceExistsError(status_code=409, message="conflict")
    )

    with pytest.raises(exceptions.CosmosResourceExistsError):
        await repo.create_conversation(conversation)

    assert container.create_item.await_count == 1


@patch("src.services.conversation_store.cosmos.CosmosClient")
@patch("azure.identity.aio.DefaultAzureCredential")
async def test_list_conversations_circuit_breaker_opens_after_repeated_failures(
    mock_credential_cls: MagicMock, mock_client_cls: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    import src.services.conversation_store.cosmos as module

    monkeypatch.setattr(module, "_RETRY_MAX_ATTEMPTS", 1)
    monkeypatch.setattr(module, "_CIRCUIT_BREAKER_FAILURE_THRESHOLD", 2)
    monkeypatch.setattr(module, "_CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS", 999.0)

    repo, container = _build_repo(mock_client_cls)
    container.query_items = MagicMock(
        side_effect=lambda **_: _async_iter_raise(ServiceRequestError("down"))
    )

    with pytest.raises(ServiceRequestError):
        await repo.list_conversations("user-1")
    with pytest.raises(ServiceRequestError):
        await repo.list_conversations("user-1")
    assert container.query_items.call_count == 2

    from src.core.resilience import CircuitBreakerOpenError

    with pytest.raises(CircuitBreakerOpenError):
        await repo.list_conversations("user-1")
    # query_items itself (the synchronous call that returns the async iterable) is never
    # invoked a third time — the circuit breaker fails fast before it.
    assert container.query_items.call_count == 2


async def _async_iter_raise(exc: Exception) -> AsyncIterator[dict[str, Any]]:
    raise exc
    yield {}  # pragma: no cover -- unreachable, makes this a generator function

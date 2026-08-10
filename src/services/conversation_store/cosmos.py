"""Cosmos DB adapter for ConversationRepository.

Authenticates with Azure AD via DefaultAzureCredential (Managed Identity-compatible) —
no keys or connection strings, matching the Bicep Cosmos module's disableLocalAuth=true
and CLAUDE.md §4.5 (Managed Identity for service-to-service authentication).

Not imported by the in-memory local-development path; only reached via
src.services.conversation_store.factory when CONVERSATION_STORE_PROVIDER=cosmos.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TypeVar

from azure.core.exceptions import ServiceRequestError, ServiceResponseError
from azure.cosmos import exceptions
from azure.cosmos.aio import ContainerProxy, CosmosClient
from azure.identity.aio import DefaultAzureCredential

from src.core.resilience import CircuitBreaker, retry_with_backoff
from src.domain.conversation import Conversation, Message

T = TypeVar("T")

_PROVIDER_NAME = "cosmos_db"

# Resilience (Architecture Review Finding A-07, CLAUDE.md principle #9). ServiceRequestError/
# ServiceResponseError (no status code — pure transport-level failure) are always retryable.
# CosmosHttpResponseError (covers CosmosResourceNotFoundError/CosmosResourceExistsError too,
# since both subclass it) is narrowed by _is_retryable_status via its own status_code — only
# 408 (timeout)/429 (RU throttling — the Cosmos SDK already retries this internally by default,
# this is defense in depth, not a duplicate primary mechanism)/500/503 (server-side) are
# retried; 404 (not found — a real, non-transient outcome get_conversation's own caller
# expects, see below)/409 (conflict)/400/401/403 are never retried.
_RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    exceptions.CosmosHttpResponseError,
    ServiceRequestError,
    ServiceResponseError,
)
_RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 503})
_RETRY_MAX_ATTEMPTS = 3
_RETRY_BASE_DELAY_SECONDS = 0.5
_RETRY_MAX_DELAY_SECONDS = 8.0
_CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
_CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS = 30.0


def _is_retryable_status(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code is None:
        # ServiceRequestError/ServiceResponseError never carry a status_code — a pure
        # transport-level failure, always transient.
        return True
    return status_code in _RETRYABLE_STATUS_CODES


class CosmosConversationRepository:
    """ConversationRepository implementation backed by Azure Cosmos DB for NoSQL."""

    def __init__(self, endpoint: str, database_name: str, container_name: str) -> None:
        self._credential = DefaultAzureCredential()
        self._client = CosmosClient(endpoint, credential=self._credential)
        self._database_name = database_name
        self._container_name = container_name
        self._circuit_breaker = CircuitBreaker(
            _PROVIDER_NAME,
            failure_threshold=_CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            reset_timeout_seconds=_CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS,
        )

    async def _resilient_call(
        self, operation: Callable[[], Awaitable[T]], *, operation_name: str
    ) -> T:
        """Shared retry+circuit-breaker wrapper for every Cosmos container operation below.
        CircuitBreakerOpenError is intentionally NOT translated to a typed exception here (no
        shared "CosmosProviderError" exists in this codebase's exception hierarchy — Cosmos
        errors are handled directly at the ConversationRepository boundary, whose Protocol
        never wraps them); it propagates as-is, still a real, informative exception."""

        async def _with_retry() -> T:
            return await retry_with_backoff(
                operation,
                retryable_exceptions=_RETRYABLE_EXCEPTIONS,
                max_attempts=_RETRY_MAX_ATTEMPTS,
                base_delay_seconds=_RETRY_BASE_DELAY_SECONDS,
                max_delay_seconds=_RETRY_MAX_DELAY_SECONDS,
                operation_name=f"{_PROVIDER_NAME} {operation_name}",
                is_retryable=_is_retryable_status,
            )

        return await self._circuit_breaker.call(_with_retry)

    async def close(self) -> None:
        await self._client.close()
        await self._credential.close()

    async def _container(self) -> ContainerProxy:
        database = self._client.get_database_client(self._database_name)
        return database.get_container_client(self._container_name)

    async def create_conversation(self, conversation: Conversation) -> Conversation:
        container = await self._container()
        item = conversation.model_dump(mode="json", by_alias=True)

        async def _create() -> dict:
            return await container.create_item(body=item)

        created = await self._resilient_call(_create, operation_name="create_item")
        return Conversation.model_validate(created)

    async def get_conversation(self, user_id: str, conversation_id: str) -> Conversation | None:
        container = await self._container()

        async def _read() -> dict:
            return await container.read_item(item=conversation_id, partition_key=user_id)

        try:
            item = await self._resilient_call(_read, operation_name="read_item")
        except exceptions.CosmosResourceNotFoundError:
            return None
        return Conversation.model_validate(item)

    async def list_conversations(self, user_id: str) -> list[Conversation]:
        container = await self._container()
        query = "SELECT * FROM c WHERE c.userId = @userId ORDER BY c.createdAt DESC"

        async def _query() -> list[dict]:
            items = container.query_items(
                query=query,
                parameters=[{"name": "@userId", "value": user_id}],
                partition_key=user_id,
            )
            return [item async for item in items]

        raw_items = await self._resilient_call(_query, operation_name="query_items")
        return [Conversation.model_validate(item) for item in raw_items]

    async def append_message(
        self,
        user_id: str,
        conversation_id: str,
        message: Message,
        metadata: dict[str, str] | None = None,
        current_agent: str | None = None,
    ) -> Conversation:
        conversation = await self.get_conversation(user_id, conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found for user {user_id}")
        conversation.messages.append(message)
        if metadata is not None:
            conversation.metadata = metadata
        if current_agent is not None:
            conversation.current_agent = current_agent
        conversation.updated_at = datetime.now(UTC)
        container = await self._container()
        body = conversation.model_dump(mode="json", by_alias=True)

        async def _upsert() -> dict:
            return await container.upsert_item(body=body)

        updated = await self._resilient_call(_upsert, operation_name="upsert_item")
        return Conversation.model_validate(updated)

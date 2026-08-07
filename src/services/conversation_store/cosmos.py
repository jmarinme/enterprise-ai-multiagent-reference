"""Cosmos DB adapter for ConversationRepository.

Authenticates with Azure AD via DefaultAzureCredential (Managed Identity-compatible) —
no keys or connection strings, matching the Bicep Cosmos module's disableLocalAuth=true
and CLAUDE.md §4.5 (Managed Identity for service-to-service authentication).

Not imported by the in-memory local-development path; only reached via
src.services.conversation_store.factory when CONVERSATION_STORE_PROVIDER=cosmos.
"""

from __future__ import annotations

from datetime import UTC, datetime

from azure.cosmos import exceptions
from azure.cosmos.aio import ContainerProxy, CosmosClient
from azure.identity.aio import DefaultAzureCredential

from src.domain.conversation import Conversation, Message


class CosmosConversationRepository:
    """ConversationRepository implementation backed by Azure Cosmos DB for NoSQL."""

    def __init__(self, endpoint: str, database_name: str, container_name: str) -> None:
        self._credential = DefaultAzureCredential()
        self._client = CosmosClient(endpoint, credential=self._credential)
        self._database_name = database_name
        self._container_name = container_name

    async def close(self) -> None:
        await self._client.close()
        await self._credential.close()

    async def _container(self) -> ContainerProxy:
        database = self._client.get_database_client(self._database_name)
        return database.get_container_client(self._container_name)

    async def create_conversation(self, conversation: Conversation) -> Conversation:
        container = await self._container()
        item = conversation.model_dump(mode="json", by_alias=True)
        created = await container.create_item(body=item)
        return Conversation.model_validate(created)

    async def get_conversation(self, user_id: str, conversation_id: str) -> Conversation | None:
        container = await self._container()
        try:
            item = await container.read_item(item=conversation_id, partition_key=user_id)
        except exceptions.CosmosResourceNotFoundError:
            return None
        return Conversation.model_validate(item)

    async def list_conversations(self, user_id: str) -> list[Conversation]:
        container = await self._container()
        query = "SELECT * FROM c WHERE c.userId = @userId ORDER BY c.createdAt DESC"
        items = container.query_items(
            query=query,
            parameters=[{"name": "@userId", "value": user_id}],
            partition_key=user_id,
        )
        return [Conversation.model_validate(item) async for item in items]

    async def append_message(
        self,
        user_id: str,
        conversation_id: str,
        message: Message,
        metadata: dict[str, str] | None = None,
    ) -> Conversation:
        conversation = await self.get_conversation(user_id, conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found for user {user_id}")
        conversation.messages.append(message)
        if metadata is not None:
            conversation.metadata = metadata
        conversation.updated_at = datetime.now(UTC)
        container = await self._container()
        updated = await container.upsert_item(
            body=conversation.model_dump(mode="json", by_alias=True)
        )
        return Conversation.model_validate(updated)

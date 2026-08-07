"""Selects a ConversationRepository implementation from configuration.

The Cosmos adapter is imported lazily, inside the cosmos branch, so that using the default
in-memory provider never requires azure-cosmos/azure-identity to be installed or reachable.
"""

from __future__ import annotations

from src.config.settings import ConversationStoreSettings
from src.domain.conversation_repository import ConversationRepository
from src.services.conversation_store.in_memory import InMemoryConversationRepository


def get_conversation_repository(settings: ConversationStoreSettings) -> ConversationRepository:
    """Return the ConversationRepository implementation selected by settings."""
    if settings.conversation_store_provider == "in_memory":
        return InMemoryConversationRepository()

    if settings.conversation_store_provider == "cosmos":
        from src.services.conversation_store.cosmos import CosmosConversationRepository

        if not settings.cosmos_db_endpoint:
            raise ValueError(
                "COSMOS_DB_ENDPOINT must be set when CONVERSATION_STORE_PROVIDER=cosmos"
            )
        return CosmosConversationRepository(
            endpoint=settings.cosmos_db_endpoint,
            database_name=settings.cosmos_db_database,
            container_name=settings.cosmos_db_container,
        )

    raise ValueError(
        f"Unsupported conversation store provider: {settings.conversation_store_provider}"
    )

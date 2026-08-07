"""Unit tests for get_conversation_repository: provider selection (PBI-03-02)."""

import pytest

from src.config.settings import ConversationStoreSettings
from src.services.conversation_store.factory import get_conversation_repository
from src.services.conversation_store.in_memory import InMemoryConversationRepository


def test_factory_returns_in_memory_provider_by_default() -> None:
    settings = ConversationStoreSettings()

    repository = get_conversation_repository(settings)

    assert isinstance(repository, InMemoryConversationRepository)


def test_factory_returns_cosmos_provider_when_configured() -> None:
    from src.services.conversation_store.cosmos import CosmosConversationRepository

    settings = ConversationStoreSettings(
        conversation_store_provider="cosmos",
        cosmos_db_endpoint="https://example.documents.azure.com:443/",
    )

    repository = get_conversation_repository(settings)

    assert isinstance(repository, CosmosConversationRepository)


def test_factory_raises_when_cosmos_endpoint_is_missing() -> None:
    settings = ConversationStoreSettings(conversation_store_provider="cosmos")

    with pytest.raises(ValueError, match="COSMOS_DB_ENDPOINT"):
        get_conversation_repository(settings)


def test_factory_raises_for_unsupported_provider() -> None:
    settings = ConversationStoreSettings.model_construct(conversation_store_provider="unsupported")

    with pytest.raises(ValueError, match="Unsupported conversation store provider"):
        get_conversation_repository(settings)

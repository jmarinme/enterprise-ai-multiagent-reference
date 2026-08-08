"""Integration test scaffold for CosmosConversationRepository.

Skipped entirely unless a real Cosmos DB endpoint is configured via COSMOS_DB_ENDPOINT — this
suite never runs against Azure automatically and requires no Azure connectivity to collect.
Also skipped if the optional `cosmos` dependency group is not installed.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("azure.cosmos")

COSMOS_DB_ENDPOINT = os.environ.get("COSMOS_DB_ENDPOINT")

pytestmark = pytest.mark.skipif(
    not COSMOS_DB_ENDPOINT,
    reason="COSMOS_DB_ENDPOINT is not set; skipping live Cosmos DB integration test",
)


async def test_create_and_retrieve_conversation_against_live_cosmos() -> None:
    from src.domain.conversation import Conversation
    from src.services.conversation_store.cosmos import CosmosConversationRepository

    assert COSMOS_DB_ENDPOINT is not None
    repo = CosmosConversationRepository(
        endpoint=COSMOS_DB_ENDPOINT,
        database_name=os.environ.get("COSMOS_DB_DATABASE", "tmxap-conversation-db"),
        container_name=os.environ.get("COSMOS_DB_CONTAINER", "conversations"),
    )
    try:
        conversation = Conversation(user_id="integration-test-synthetic-user")
        created = await repo.create_conversation(conversation)

        retrieved = await repo.get_conversation(conversation.user_id, created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
    finally:
        await repo.close()

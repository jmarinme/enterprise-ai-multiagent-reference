"""Unit tests for InMemoryConversationRepository: create, retrieve, list, append-message,
and ordering behavior. Requires no Azure or Cosmos DB connectivity.
"""

from src.domain.conversation import Conversation, Message, MessageRole
from src.services.conversation_store.in_memory import InMemoryConversationRepository


async def test_create_and_retrieve_conversation() -> None:
    repo = InMemoryConversationRepository()
    conversation = Conversation(user_id="user-1")

    created = await repo.create_conversation(conversation)
    retrieved = await repo.get_conversation("user-1", created.id)

    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.user_id == "user-1"


async def test_get_conversation_returns_none_when_not_found() -> None:
    repo = InMemoryConversationRepository()

    result = await repo.get_conversation("user-1", "does-not-exist")

    assert result is None


async def test_list_conversations_returns_only_matching_user_newest_first() -> None:
    repo = InMemoryConversationRepository()
    older = Conversation(user_id="user-1")
    newer = Conversation(user_id="user-1")
    other_user = Conversation(user_id="user-2")

    await repo.create_conversation(older)
    await repo.create_conversation(other_user)
    # Force a distinct, later created_at than `older` to make ordering deterministic.
    from datetime import timedelta

    newer.created_at = older.created_at + timedelta(seconds=1)
    await repo.create_conversation(newer)

    results = await repo.list_conversations("user-1")

    assert [c.id for c in results] == [newer.id, older.id]


async def test_append_message_adds_message_and_updates_timestamp() -> None:
    repo = InMemoryConversationRepository()
    conversation = await repo.create_conversation(Conversation(user_id="user-1"))
    message = Message(role=MessageRole.USER, content="Where is my claim?")

    updated = await repo.append_message("user-1", conversation.id, message)

    assert len(updated.messages) == 1
    assert updated.messages[0].content == "Where is my claim?"
    assert updated.updated_at >= conversation.updated_at


async def test_append_message_preserves_order_across_multiple_appends() -> None:
    repo = InMemoryConversationRepository()
    conversation = await repo.create_conversation(Conversation(user_id="user-1"))

    await repo.append_message(
        "user-1", conversation.id, Message(role=MessageRole.USER, content="first")
    )
    await repo.append_message(
        "user-1", conversation.id, Message(role=MessageRole.ASSISTANT, content="second")
    )
    final = await repo.append_message(
        "user-1", conversation.id, Message(role=MessageRole.USER, content="third")
    )

    assert [m.content for m in final.messages] == ["first", "second", "third"]


async def test_append_message_replaces_metadata_when_provided() -> None:
    repo = InMemoryConversationRepository()
    conversation = await repo.create_conversation(
        Conversation(user_id="user-1", metadata={"claimsIntakeState": "v1"})
    )

    updated = await repo.append_message(
        "user-1",
        conversation.id,
        Message(role=MessageRole.ASSISTANT, content="reply"),
        metadata={"claimsIntakeState": "v2"},
    )

    assert updated.metadata == {"claimsIntakeState": "v2"}


async def test_append_message_leaves_metadata_untouched_when_not_provided() -> None:
    repo = InMemoryConversationRepository()
    conversation = await repo.create_conversation(
        Conversation(user_id="user-1", metadata={"claimsIntakeState": "v1"})
    )

    updated = await repo.append_message(
        "user-1", conversation.id, Message(role=MessageRole.USER, content="hi")
    )

    assert updated.metadata == {"claimsIntakeState": "v1"}


async def test_append_message_updates_current_agent_when_provided() -> None:
    """PBI-05-01: current_agent must reflect whichever Agent most recently handled a turn, not
    stay frozen at whichever Agent handled conversation creation — otherwise a legitimate
    cross-domain handoff (Claims -> Broker) would be invisible to the Supervisor's own
    "stay with the current agent on an ambiguous follow-up" fallback."""
    repo = InMemoryConversationRepository()
    conversation = await repo.create_conversation(
        Conversation(user_id="user-1", current_agent="ClaimsAgent")
    )

    updated = await repo.append_message(
        "user-1",
        conversation.id,
        Message(role=MessageRole.ASSISTANT, content="reply"),
        current_agent="BrokerAgent",
    )

    assert updated.current_agent == "BrokerAgent"


async def test_append_message_leaves_current_agent_untouched_when_not_provided() -> None:
    repo = InMemoryConversationRepository()
    conversation = await repo.create_conversation(
        Conversation(user_id="user-1", current_agent="ClaimsAgent")
    )

    updated = await repo.append_message(
        "user-1", conversation.id, Message(role=MessageRole.USER, content="hi")
    )

    assert updated.current_agent == "ClaimsAgent"


async def test_append_message_raises_for_unknown_conversation() -> None:
    repo = InMemoryConversationRepository()
    message = Message(role=MessageRole.USER, content="hello")

    try:
        await repo.append_message("user-1", "missing-conversation", message)
    except ValueError:
        return
    raise AssertionError("Expected ValueError for unknown conversation")


async def test_stored_state_is_isolated_from_external_mutation() -> None:
    repo = InMemoryConversationRepository()
    conversation = await repo.create_conversation(Conversation(user_id="user-1"))

    conversation.messages.append(Message(role=MessageRole.USER, content="mutated externally"))

    retrieved = await repo.get_conversation("user-1", conversation.id)
    assert retrieved is not None
    assert retrieved.messages == []

"""Unit tests for load_conversation_context."""

from src.domain.conversation import Conversation, Message, MessageRole
from src.services.conversation_store.in_memory import InMemoryConversationRepository
from src.supervisor.context import load_conversation_context


async def test_returns_new_context_when_conversation_id_is_none() -> None:
    repository = InMemoryConversationRepository()

    context = await load_conversation_context(repository, user_id="user-1", conversation_id=None)

    assert context.is_new is True
    assert context.user_id == "user-1"
    assert context.messages == []
    assert context.conversation_id


async def test_returns_new_context_when_conversation_id_not_found() -> None:
    repository = InMemoryConversationRepository()

    context = await load_conversation_context(
        repository, user_id="user-1", conversation_id="does-not-exist"
    )

    assert context.is_new is True
    assert context.conversation_id == "does-not-exist"


async def test_returns_existing_context_when_conversation_found() -> None:
    repository = InMemoryConversationRepository()
    conversation = await repository.create_conversation(
        Conversation(
            user_id="user-1",
            messages=[Message(role=MessageRole.USER, content="hi")],
        )
    )

    context = await load_conversation_context(
        repository, user_id="user-1", conversation_id=conversation.id
    )

    assert context.is_new is False
    assert context.conversation_id == conversation.id
    assert len(context.messages) == 1
    assert context.messages[0].content == "hi"


async def test_truncates_history_to_max_history_messages() -> None:
    repository = InMemoryConversationRepository()
    messages = [Message(role=MessageRole.USER, content=str(i)) for i in range(5)]
    conversation = await repository.create_conversation(
        Conversation(user_id="user-1", messages=messages)
    )

    context = await load_conversation_context(
        repository,
        user_id="user-1",
        conversation_id=conversation.id,
        max_history_messages=2,
    )

    assert [m.content for m in context.messages] == ["3", "4"]


async def test_zero_max_history_messages_disables_truncation() -> None:
    repository = InMemoryConversationRepository()
    messages = [Message(role=MessageRole.USER, content=str(i)) for i in range(5)]
    conversation = await repository.create_conversation(
        Conversation(user_id="user-1", messages=messages)
    )

    context = await load_conversation_context(
        repository,
        user_id="user-1",
        conversation_id=conversation.id,
        max_history_messages=0,
    )

    assert len(context.messages) == 5

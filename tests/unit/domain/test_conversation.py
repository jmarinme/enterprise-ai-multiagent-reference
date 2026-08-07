"""Unit tests for the Conversation/Message domain models."""

from src.domain.conversation import Conversation, ConversationStatus, Message, MessageRole


def test_conversation_defaults_conversation_id_to_id() -> None:
    conversation = Conversation(user_id="user-synthetic-1")

    assert conversation.conversation_id == conversation.id
    assert conversation.status == ConversationStatus.ACTIVE
    assert conversation.messages == []


def test_conversation_serializes_to_camel_case_for_cosmos() -> None:
    conversation = Conversation(user_id="user-synthetic-1", current_agent="claims")

    payload = conversation.model_dump(mode="json", by_alias=True)

    assert payload["userId"] == "user-synthetic-1"
    assert payload["currentAgent"] == "claims"
    assert "createdAt" in payload
    assert "updatedAt" in payload


def test_conversation_round_trips_from_camel_case_payload() -> None:
    conversation = Conversation(user_id="user-synthetic-1")
    payload = conversation.model_dump(mode="json", by_alias=True)

    restored = Conversation.model_validate(payload)

    assert restored.user_id == conversation.user_id
    assert restored.id == conversation.id


def test_message_defaults_role_and_id() -> None:
    message = Message(role=MessageRole.USER, content="Hello")

    assert message.role == MessageRole.USER
    assert message.id
    assert message.correlation_id is None

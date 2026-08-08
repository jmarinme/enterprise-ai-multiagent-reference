"""API-level tests for GET /conversations and GET /conversations/{conversationId} (PBI-04-04):
exercises the full ConversationRepository -> JSON pipeline through the real FastAPI app.

The userId query parameter must be accepted as camelCase ("userId") on the wire, matching this
API's existing convention (POST /chat's ChatRequest/ChatResponse are camelCase) — a real bug
where the route only accepted the bare Python parameter name ("user_id") was caught via live
DEV validation and is regression-guarded here.
"""

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_list_conversations_accepts_the_camelcase_userid_query_parameter() -> None:
    response = client.get("/conversations", params={"userId": "conv-list-user-1"})

    assert response.status_code == 200
    assert response.json() == []


def test_list_conversations_rejects_the_snake_case_query_parameter() -> None:
    """Regression guard for the exact shape of the bug found live: FastAPI does not
    camelCase-alias plain function parameters automatically — only Pydantic body models with
    an alias_generator do that. "user_id" must NOT work; only "userId" should."""
    response = client.get("/conversations", params={"user_id": "conv-list-user-1"})

    assert response.status_code == 422


def test_list_conversations_returns_a_conversation_after_a_chat_turn() -> None:
    user_id = "conv-list-user-2"
    chat_response = client.post("/chat", json={"message": "hola", "userId": user_id})
    assert chat_response.status_code == 200
    conversation_id = chat_response.json()["conversationId"]

    response = client.get("/conversations", params={"userId": user_id})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["conversationId"] == conversation_id
    assert body[0]["title"]
    assert body[0]["status"] == "active"


def test_get_conversation_returns_the_full_message_history() -> None:
    user_id = "conv-detail-user-1"
    chat_response = client.post(
        "/chat", json={"message": "Quiero conocer mis comisiones.", "userId": user_id}
    )
    conversation_id = chat_response.json()["conversationId"]

    response = client.get(f"/conversations/{conversation_id}", params={"userId": user_id})

    assert response.status_code == 200
    body = response.json()
    assert body["conversationId"] == conversation_id
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][0]["content"] == "Quiero conocer mis comisiones."
    assert body["messages"][1]["role"] == "assistant"


def test_get_conversation_returns_404_for_an_unknown_conversation() -> None:
    response = client.get(
        "/conversations/does-not-exist", params={"userId": "conv-detail-user-1"}
    )

    assert response.status_code == 404


def test_get_conversation_title_is_derived_from_the_first_user_message() -> None:
    user_id = "conv-title-user-1"
    client.post("/chat", json={"message": "Necesito una cotización.", "userId": user_id})

    response = client.get("/conversations", params={"userId": user_id})

    assert response.status_code == 200
    assert response.json()[0]["title"] == "Necesito una cotización."

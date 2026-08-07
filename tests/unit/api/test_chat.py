"""API-level tests for POST /chat: exercises the full Supervisor -> Intent -> Registry ->
Agent -> Repository -> JSON pipeline through the real FastAPI app.
"""

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_chat_returns_expected_shape_for_a_claims_message() -> None:
    response = client.post(
        "/chat",
        json={"message": "I need to file a claim", "userId": "user-1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["agent"] == "ClaimsAgent"
    assert body["intent"] == "CLAIMS"
    assert isinstance(body["response"], str) and body["response"]
    assert body["conversationId"]


def test_chat_returns_fallback_agent_for_an_unmatched_message() -> None:
    response = client.post(
        "/chat",
        json={"message": "hello, good morning", "userId": "user-1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["agent"] == "FallbackAgent"
    assert body["intent"] == "UNKNOWN"


def test_chat_persists_and_reuses_the_conversation_id_across_turns() -> None:
    first = client.post(
        "/chat",
        json={"message": "broker commission question", "userId": "user-persist-test"},
    )
    conversation_id = first.json()["conversationId"]

    second = client.post(
        "/chat",
        json={
            "message": "another broker question",
            "userId": "user-persist-test",
            "conversationId": conversation_id,
        },
    )

    assert second.status_code == 200
    assert second.json()["conversationId"] == conversation_id


def test_chat_rejects_a_request_missing_required_fields() -> None:
    response = client.post("/chat", json={"message": "hi"})

    assert response.status_code == 422

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
    assert "metadata" in body


def test_chat_drives_a_full_claim_report_end_to_end_through_the_real_api() -> None:
    """PBI-01-05 success criteria: a complete multi-turn claim report, entirely through
    POST /chat, with no direct Agent/Tool access — proves Supervisor -> ClaimsAgent ->
    ToolExecutor -> synthetic Tools -> ConversationRepository metadata round trip all work
    together through the actual FastAPI app."""
    user_id = "user-claim-e2e"
    conversation_id: str | None = None
    final_response = ""

    for message in [
        "I need to report a claim",
        "SYN-POL-0001",
        "2026-08-01",
        "In my driveway",
        "It was a collision",
        "Another car hit me while parked",
        "Jane Caller",
        "555-123-4567",
        "no",
        "yes",
    ]:
        payload = {"message": message, "userId": user_id}
        if conversation_id:
            payload["conversationId"] = conversation_id
        result = client.post("/chat", json=payload)
        assert result.status_code == 200
        body = result.json()
        conversation_id = body["conversationId"]
        final_response = body["response"]

    assert "SYN-CLM-" in final_response
    assert "assigned" in final_response.lower()


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

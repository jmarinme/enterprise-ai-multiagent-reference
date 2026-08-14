"""API-level tests for the observability read endpoints (PBI-13-01 §19): exercises the full
POST /chat -> ObservabilityService.record_run -> GET /observability/* pipeline through the real
FastAPI app, using the same auth-override/in-memory-store test infrastructure as
test_conversations.py.
"""

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


@pytest.mark.no_auth_override
def test_get_summary_requires_a_bearer_token_when_unauthenticated() -> None:
    """Anonymous users must never access Observability (PBI-13-01 §16) — real auth dependency,
    no override (see tests/conftest.py's no_auth_override marker semantics)."""
    response = TestClient(app).get("/observability/summary")

    assert response.status_code == 401


def test_summary_and_conversation_list_reflect_a_real_chat_turn() -> None:
    user_id = "obs-route-user-1"
    chat_response = client.post(
        "/chat", json={"message": "Quiero reportar un siniestro.", "userId": user_id}
    )
    assert chat_response.status_code == 200
    conversation_id = chat_response.json()["conversationId"]

    summary_response = client.get("/observability/summary")
    assert summary_response.status_code == 200
    summary_body = summary_response.json()
    assert summary_body["conversationCount"] >= 1
    assert summary_body["runCount"] >= 1

    list_response = client.get("/observability/conversations", params={"limit": 10})
    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body["limit"] == 10
    assert list_body["skip"] == 0
    assert any(item["conversationId"] == conversation_id for item in list_body["items"])


def test_conversation_detail_correlates_messages_and_runs() -> None:
    user_id = "obs-route-user-2"
    chat_response = client.post(
        "/chat", json={"message": "Necesito ayuda con mi comisión.", "userId": user_id}
    )
    conversation_id = chat_response.json()["conversationId"]

    response = client.get(f"/observability/conversations/{conversation_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["conversationId"] == conversation_id
    assert len(body["messages"]) == 2
    assert len(body["runs"]) == 1
    # The assistant message must carry the run_id that produced it.
    assistant_message = next(m for m in body["messages"] if m["role"] == "assistant")
    assert assistant_message["runId"] == body["runs"][0]["runId"]


def test_conversation_detail_returns_404_for_an_unknown_conversation() -> None:
    response = client.get("/observability/conversations/does-not-exist")

    assert response.status_code == 404


def test_run_detail_is_fetchable_by_id() -> None:
    user_id = "obs-route-user-3"
    chat_response = client.post("/chat", json={"message": "Hola", "userId": user_id})
    conversation_id = chat_response.json()["conversationId"]
    detail = client.get(f"/observability/conversations/{conversation_id}").json()
    run_id = detail["runs"][0]["runId"]

    response = client.get(f"/observability/runs/{run_id}")

    assert response.status_code == 200
    assert response.json()["runId"] == run_id


def test_run_detail_returns_404_for_an_unknown_run() -> None:
    response = client.get("/observability/runs/does-not-exist")

    assert response.status_code == 404


def test_conversation_list_pagination_never_exceeds_the_requested_limit() -> None:
    response = client.get("/observability/conversations", params={"skip": 0, "limit": 1})

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) <= 1
    assert body["limit"] == 1

"""Regression test for PBI-13-01's chat.py fix: correlation_id was generated/propagated by
CorrelationIdMiddleware but was never previously threaded into AgentRequest. Verified here via
the observability pipeline (RunRecord.trace_id), since GET /conversations does not expose
correlation_id on the wire.
"""

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_a_client_supplied_correlation_id_flows_through_to_the_recorded_run() -> None:
    correlation_id = "test-correlation-id-12345"
    user_id = "corr-test-user-1"

    chat_response = client.post(
        "/chat",
        json={"message": "Hola", "userId": user_id},
        headers={"X-Correlation-ID": correlation_id},
    )

    assert chat_response.status_code == 200
    assert chat_response.headers["X-Correlation-ID"] == correlation_id
    conversation_id = chat_response.json()["conversationId"]

    detail = client.get(f"/observability/conversations/{conversation_id}").json()

    assert len(detail["runs"]) == 1
    assert detail["runs"][0]["traceId"] == correlation_id


def test_a_missing_correlation_id_still_generates_one_and_records_it() -> None:
    user_id = "corr-test-user-2"

    chat_response = client.post("/chat", json={"message": "Hola", "userId": user_id})

    assert chat_response.status_code == 200
    generated = chat_response.headers["X-Correlation-ID"]
    assert generated
    conversation_id = chat_response.json()["conversationId"]

    detail = client.get(f"/observability/conversations/{conversation_id}").json()

    assert detail["runs"][0]["traceId"] == generated

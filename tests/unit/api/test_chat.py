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


def test_chat_claims_response_includes_typed_citations_through_the_real_api() -> None:
    """PBI-02-01/PBI-02-03: proves KnowledgeRetriever and Grounder are genuinely wired through
    the real composition root (apps/api/src/api/dependencies.py), not just in isolated unit
    tests — a message matching the shipped synthetic knowledge base produces typed citations
    and grounding metadata in the JSON response, not an inline text annotation."""
    response = client.post(
        "/chat",
        json={"message": "I need to report a claim after hours", "userId": "user-knowledge-e2e"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["agent"] == "ClaimsAgent"
    assert len(body["citations"]) > 0
    assert body["citations"][0]["documentId"].startswith("KB-CLAIMS-")
    assert body["groundingMetadata"]["isGrounded"] is True


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


def test_chat_drives_a_full_commission_conversation_end_to_end_through_the_real_api() -> None:
    """PBI-01-06 success criteria: a complete commission inquiry, entirely through POST /chat,
    ending in a registered synthetic commission-payment request — proves Supervisor ->
    BrokerAgent -> ToolExecutor -> synthetic Tools -> ConversationRepository metadata round
    trip all work together through the actual FastAPI app, including an ambiguous follow-up
    ("SYN-BRK-0001 2026-Q1" has no BROKER keyword) staying routed to BrokerAgent."""
    user_id = "user-commission-e2e"
    conversation_id: str | None = None
    final_response = ""
    agents_seen: list[str] = []

    for message in [
        "I need to check my commissions.",
        "SYN-BRK-0001 2026-Q1",
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
        agents_seen.append(body["agent"])

    assert agents_seen == ["BrokerAgent", "BrokerAgent", "BrokerAgent"]
    assert "SYN-PAYREQ-" in final_response


def test_chat_drives_a_full_policy_status_conversation_end_to_end_through_the_real_api() -> None:
    """PBI-01-06's own literal example phrasing ("I want to know the status of a policy.")
    must reach BrokerAgent through the real intent resolver — this exact scenario surfaced a
    real RuleBasedIntentResolver gap during live validation (see decisions.md) before
    _BROKER_KEYWORDS included a bare "policy" keyword."""
    user_id = "user-policy-status-e2e"
    conversation_id: str | None = None
    final_response = ""
    agents_seen: list[str] = []

    for message in ["I want to know the status of a policy.", "SYN-POL-0001"]:
        payload = {"message": message, "userId": user_id}
        if conversation_id:
            payload["conversationId"] = conversation_id
        result = client.post("/chat", json=payload)
        assert result.status_code == 200
        body = result.json()
        conversation_id = body["conversationId"]
        final_response = body["response"]
        agents_seen.append(body["agent"])

    assert agents_seen == ["BrokerAgent", "BrokerAgent"]
    assert "active" in final_response.lower()


def test_chat_drives_a_full_commercial_intake_conversation_end_to_end_through_the_real_api() -> (
    None
):
    """PBI-01-07 success criteria: a complete commercial lead intake, entirely through
    POST /chat, ending in a registered synthetic lead — proves Supervisor ->
    CommercialIntakeAgent -> ToolExecutor -> LeadRegistrationTool -> ConversationRepository
    metadata round trip all work together through the actual FastAPI app. Every follow-up
    after the first message ("Acme Consulting LLC", "Jane Doe", "email please", ...) contains
    no COMMERCIAL/CLAIMS/BROKER keyword, so this also exercises the Supervisor's
    ambiguous-follow-up routing-continuity fallback (PBI-01-05) end to end for the third
    agent it applies to."""
    user_id = "user-commercial-e2e"
    conversation_id: str | None = None
    final_response = ""
    agents_seen: list[str] = []

    for message in [
        "I'd like a quote for new business coverage",
        "Acme Consulting LLC",
        "Jane Doe",
        "email please",
        "jane@example.com",
        "general liability",
        "We provide small business consulting services.",
    ]:
        payload = {"message": message, "userId": user_id}
        if conversation_id:
            payload["conversationId"] = conversation_id
        result = client.post("/chat", json=payload)
        assert result.status_code == 200
        body = result.json()
        conversation_id = body["conversationId"]
        final_response = body["response"]
        agents_seen.append(body["agent"])

    assert agents_seen == ["CommercialIntakeAgent"] * 7
    assert "SYN-LEAD-" in final_response


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

"""API-level tests for POST /chat: exercises the full Supervisor -> Intent -> Registry ->
Agent -> Repository -> JSON pipeline through the real FastAPI app.
"""

import asyncio

from api.dependencies import get_conversation_repository_dep
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
    # PBI-02-03/PBI-02-04: always present in the JSON contract, additive/backward-compatible.
    assert isinstance(body["citations"], list)
    # No LLM-requested Tool call for a plain "file a claim" opener — the default, unscripted
    # MockLLMProvider composition-root instance never requests one (see
    # src/llm/mock_provider.py).
    assert body["toolCalls"] == []


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

    # PBI-04-04: a direct policy number short-circuits customer discovery (no customer_name
    # question), and an explicit yes/no confirmation is now required after policy/payment/
    # coverage validation before the claim is actually registered — hence the trailing "yes".
    for message in [
        "I need to report a claim",
        "SYN-POL-0001",
        "2026-08-01",
        "In my driveway",
        "It was a collision",
        "Another car hit me while parked",
        "555-123-4567",
        "no",
        "yes",
        "yes",  # vehicle_drivable (PBI-05-01: auto profile asks this)
        "yes",  # explicit confirmation before registration (PBI-04-04)
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
        # PBI-14-03 section 11: explicit pre-registration confirmation is now required.
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

    assert agents_seen == ["CommercialIntakeAgent"] * 8
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
    # PBI-11-01: userId is now deprecated/optional (identity comes from the authenticated
    # token, not the request body) — message remains the one genuinely required field.
    response = client.post("/chat", json={"userId": "user-1"})

    assert response.status_code == 422


def test_chat_accepts_a_request_with_no_userid_at_all() -> None:
    """PBI-11-01 regression guard: userId is deprecated — a client that stops sending it
    entirely must still be accepted (identity comes from the Bearer token)."""
    response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 200


def test_chat_hands_off_from_claims_to_broker_and_preserves_claims_state() -> None:
    """PBI-05-01 requirement 5 (SCENARIO C shape): a mid-Claims conversation that switches
    domain ("Ahora quiero consultar mis comisiones.") must hand off to BrokerAgent, and the
    in-progress Claims state must not be silently destroyed — it survives in the conversation's
    stored metadata even though BrokerAgent answered the intervening turns, so a caller could
    still return to it later (src.agents.shared.state_persistence.carry_forward_other_agent_state)."""
    user_id = "user-handoff-e2e"

    first = client.post(
        "/chat",
        json={"message": "Quiero reportar un accidente, tuve un choque.", "userId": user_id},
    )
    assert first.status_code == 200
    conversation_id = first.json()["conversationId"]
    assert first.json()["agent"] == "ClaimsAgent"

    second = client.post(
        "/chat",
        json={
            "message": "Ahora quiero consultar mis comisiones. Soy Synthetic Brokerage One.",
            "userId": user_id,
            "conversationId": conversation_id,
        },
    )
    assert second.status_code == 200
    assert second.json()["agent"] == "BrokerAgent"

    # The Claims state from turn 1 must survive BrokerAgent answering turn 2 — even though
    # AgentResponse.metadata replaces (not merges) the conversation's stored metadata each turn.
    stored = asyncio.run(get_conversation_repository_dep().get_conversation(user_id, conversation_id))
    assert stored is not None
    assert "claimsIntakeState" in stored.metadata
    assert "brokerInquiryState" in stored.metadata

    third = client.post(
        "/chat",
        json={
            "message": "las del primer trimestre de 2026",
            "userId": user_id,
            "conversationId": conversation_id,
        },
    )
    assert third.status_code == 200
    # A bare period expression with no Claims/Commercial keyword must stay with Broker, not be
    # misrouted back to Claims by naive keyword matching.
    assert third.json()["agent"] == "BrokerAgent"
    assert "SYN-BRK" not in third.json()["response"]  # no raw internal broker ID leaked

    fourth = client.post(
        "/chat",
        json={
            "message": "Ahora necesito una cotización para mi empresa.",
            "userId": user_id,
            "conversationId": conversation_id,
        },
    )
    assert fourth.status_code == 200
    assert fourth.json()["agent"] == "CommercialIntakeAgent"

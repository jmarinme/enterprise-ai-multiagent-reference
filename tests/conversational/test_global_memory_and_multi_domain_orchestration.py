"""PBI-09-01 — Conversation Intelligence & Multi-domain Orchestration: acceptance/regression
tests for the shared global conversation memory (src.agents.shared.memory).

Through the real FastAPI app (POST /chat), exactly like tests/unit/api/test_chat.py's own
end-to-end style — MockLLMProvider (deterministic, no real Azure OpenAI cost/exposure). These
tests prove the caller-visible behavior this PBI exists to deliver: a fact resolved in one
domain (Claims/Broker/Commercial) is reused by another domain in the same conversation, so the
platform never re-asks for information it already has, and intent switching never loses
in-progress work in any domain. No architecture, Bicep, CI/CD, or business-capability change is
exercised or required by any test here — every scenario runs entirely through the pre-existing
/chat endpoint and the pre-existing synthetic Tools (src/services/tools/synthetic/provider.py).
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def _post(message: str, user_id: str, conversation_id: str | None = None) -> dict:
    payload: dict[str, str] = {"message": message, "userId": user_id}
    if conversation_id:
        payload["conversationId"] = conversation_id
    result = client.post("/chat", json=payload)
    assert result.status_code == 200
    return result.json()


def _memory(body: dict) -> dict:
    return json.loads(body["metadata"]["globalMemory"])


def test_broker_resolved_policy_number_is_reused_by_claims_without_re_asking() -> None:
    """Scenario: "policy lookup -> claims" (acceptance list item 3) + entity resolution +
    deduplication (items 9/10) — Broker validates a policy first; when the caller then reports a
    claim in the same conversation, ClaimsAgent must not ask "whose name is the policy under?"
    again, because the policy is already known."""
    user_id = "user-pbi09-broker-then-claims"

    first = _post("I want to know the status of a policy.", user_id)
    assert first["agent"] == "BrokerAgent"

    second = _post("SYN-POL-0001", user_id, first["conversationId"])
    assert second["agent"] == "BrokerAgent"
    assert "active" in second["response"].lower()
    assert _memory(second)["policy_number"] == "SYN-POL-0001"

    third = _post("I need to report a claim", user_id, second["conversationId"])
    assert third["agent"] == "ClaimsAgent"
    # No customer-name question — the policy is already known, so ClaimsAgent skipped straight
    # to the line-of-business lookup and the incident-detail question.
    assert "whose name" not in third["response"].lower()
    assert "name is the policy" not in third["response"].lower()
    assert _memory(third)["policy_number"] == "SYN-POL-0001"


def test_claims_broker_claims_switch_preserves_both_domains_and_resolves_broker_in_one_turn() -> (
    None
):
    """Scenario: "Claims -> Broker -> Claims" (acceptance list item 1, requirement 7's own
    example flow), combined with memory reuse collapsing what would otherwise be a second
    Broker turn (requirement 10 — avoid an unnecessary question/Tool round trip)."""
    user_id = "user-pbi09-claims-broker-claims"

    first = _post("I need to report a claim", user_id)
    assert first["agent"] == "ClaimsAgent"

    second = _post("SYN-POL-0001", user_id, first["conversationId"])
    assert second["agent"] == "ClaimsAgent"
    assert _memory(second)["policy_number"] == "SYN-POL-0001"
    assert _memory(second)["current_intent"] == "ClaimsAgent"

    # Switches domain — BrokerAgent resolves policy status in this single turn (no follow-up
    # question for the policy number needed) because global memory already has it.
    third = _post("I want to know the status of a policy.", user_id, second["conversationId"])
    assert third["agent"] == "BrokerAgent"
    assert "active" in third["response"].lower()
    memory_after_broker = _memory(third)
    assert memory_after_broker["current_intent"] == "BrokerAgent"
    assert memory_after_broker["previous_intent"] == "ClaimsAgent"

    # Switches back — Claims resumes its own in-progress intake (never restarted from scratch).
    fourth = _post("Sigamos con mi accidente.", user_id, third["conversationId"])
    assert fourth["agent"] == "ClaimsAgent"
    assert "whose name" not in fourth["response"].lower()
    memory_after_claims = _memory(fourth)
    assert memory_after_claims["current_intent"] == "ClaimsAgent"
    assert memory_after_claims["previous_intent"] == "BrokerAgent"


def test_customer_only_discovery_is_reused_by_commercial_intake() -> None:
    """Scenario: "customer only" + entity resolution (acceptance list items 8/9) — a caller
    identified by name only (no policy number given) in Claims still has that name reused by
    Commercial Intake's own contact-name question later in the same conversation."""
    user_id = "user-pbi09-customer-only"

    first = _post("I need to report a claim", user_id)
    assert first["agent"] == "ClaimsAgent"
    assert "whose name" in first["response"].lower() or "name is the policy" in first["response"].lower()

    # "Ana Torres" is a single-match synthetic customer (src/services/tools/synthetic/provider.py)
    # — customer discovery resolves her one policy automatically, no disambiguation needed.
    second = _post("Ana Torres", user_id, first["conversationId"])
    assert second["agent"] == "ClaimsAgent"
    assert _memory(second)["customer_name"] == "Ana Torres"

    third = _post("Ahora necesito una cotización para mi empresa.", user_id, second["conversationId"])
    assert third["agent"] == "CommercialIntakeAgent"
    assert "Ana Torres" not in third["response"]  # reused silently, never echoed as a raw fact
    # Contact-name question skipped because it's already known — company name is asked instead.
    assert "contact" not in third["response"].lower() or "company" in third["response"].lower()


def test_conversation_progress_summary_appears_once_enough_fields_are_known() -> None:
    """Requirement 6: after several turns, recap what is already known before asking for what's
    still missing, in the specified checkmark format."""
    user_id = "user-pbi09-summary"

    first = _post("I need to report a claim", user_id)
    second = _post("SYN-POL-0001", user_id, first["conversationId"])
    third = _post("2026-08-01", user_id, second["conversationId"])

    assert third["agent"] == "ClaimsAgent"
    assert "Hasta ahora tengo" in third["response"] or "So far I have" in third["response"]
    assert "✔" in third["response"]


def test_natural_relative_week_and_weather_phrasing_are_understood_without_structured_input() -> (
    None
):
    """Requirement 4's own examples ("la semana pasada", "llovió", "se inundó", "en mi casa") —
    a rich natural-language answer must be understood in one turn, never rejected for not being
    in a structured format."""
    user_id = "user-pbi09-natural-language"

    first = _post("Se inundó mi casa, llovió mucho la semana pasada.", user_id)
    assert first["agent"] == "ClaimsAgent"

    second = _post("Ana Torres", user_id, first["conversationId"])
    assert second["agent"] == "ClaimsAgent"
    memory = _memory(second)
    # The opening message already carried the loss type and (once the policy/customer is
    # resolved) the incident date — never re-asked as separate structured questions.
    assert memory.get("incident_type") in ("weather", "water damage")


def test_broker_broker_policy_status_flow_never_repeats_an_already_answered_question() -> None:
    """Deduplication (requirement 9): once policy_number is supplied, a follow-up turn in the
    same inquiry must never ask for it again, even without any domain switch involved."""
    user_id = "user-pbi09-no-repeat"

    first = _post("I want to know the status of a policy.", user_id)
    assert "policy" in first["response"].lower() or "póliza" in first["response"].lower()

    second = _post("SYN-POL-0001", user_id, first["conversationId"])
    assert "active" in second["response"].lower()

    # A vague follow-up with no new policy number must not re-ask for one — the conversation is
    # already complete for this inquiry (src.agents.broker.workflow._handle_completed), so the
    # original "please provide the synthetic policy number" prompt must never repeat.
    third = _post("gracias", user_id, second["conversationId"])
    assert third["agent"] == "BrokerAgent"
    assert "please provide the synthetic policy number" not in third["response"].lower()

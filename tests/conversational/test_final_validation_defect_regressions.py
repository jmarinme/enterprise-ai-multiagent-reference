"""PBI-09-01 — Final Conversational Validation: regression tests for defects found by running
realistic, live multi-turn conversations through the real FastAPI app (POST /chat,
MockLLMProvider, synthetic data — not just unit tests, per the validation task's own explicit
instruction). Each test here reproduces the exact scenario that surfaced the defect.
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


def test_domain_reentry_does_not_misattribute_the_switch_back_message_as_an_answer() -> None:
    """Defect: "Let's continue with my claim from before." — the exact message that routes the
    conversation back into ClaimsAgent from BrokerAgent — was being silently swallowed by the
    free-text fallback as the answer to whatever field ClaimsAgent had last asked several turns
    earlier (event_location here), corrupting real claim data. A domain re-entry message must
    be re-asked for, not guessed at."""
    user_id = "user-regress-reentry-location"

    first = _post("I need to report a claim, I had a collision.", user_id)
    second = _post("SYN-POL-0001", user_id, first["conversationId"])
    assert "date" in second["response"].lower() or "where" in second["response"].lower()

    # Switch away before the location question is ever actually answered.
    third = _post("I want to know the status of a policy.", user_id, second["conversationId"])
    assert third["agent"] == "BrokerAgent"

    # Switch back — this exact phrase must not become "the answer" to a stale question.
    fourth = _post(
        "Let's continue with my claim from before.", user_id, third["conversationId"]
    )
    assert fourth["agent"] == "ClaimsAgent"
    assert "let's continue" not in fourth["response"].lower()
    assert "where did the incident take place" in fourth["response"].lower()


def test_domain_reentry_does_not_misattribute_the_switch_back_message_as_a_customer_name() -> (
    None
):
    """Same defect class, different field: re-entering Claims while customer_name is still the
    pending question must re-ask cleanly, not attempt a customer_lookup for the routing phrase
    itself. Before the fix, "En realidad, volvamos a mi accidente." was sent verbatim to
    customer_lookup and correctly failed to match — but should never have been attempted at
    all."""
    user_id = "user-regress-reentry-customer-name"

    first = _post("Quiero reportar un accidente.", user_id)
    second = _post("Ahora quiero consultar mis comisiones.", user_id, first["conversationId"])
    assert second["agent"] == "BrokerAgent"
    third = _post(
        "Mejor necesito una cotizacion para mi empresa.", user_id, second["conversationId"]
    )
    assert third["agent"] == "CommercialIntakeAgent"

    fourth = _post("En realidad, volvamos a mi accidente.", user_id, third["conversationId"])
    assert fourth["agent"] == "ClaimsAgent"
    assert "no encontré" not in fourth["response"].lower()
    assert "a nombre de quién" in fourth["response"].lower()
    # The visible response looked fine even in the broken version — the corruption was
    # invisible, silently sitting in memory (event_location = "realidad, volvamos a mi
    # accidente") where it would have permanently blocked the real location from ever being
    # asked for. Assert the memory itself is clean, not just the visible text.
    assert not _memory(fourth).get("location")


def test_broker_combined_question_captures_a_bare_broker_name_with_no_prefix() -> None:
    """Defect: BrokerAgent's combined "broker name + period" prompt never set last_asked_field,
    so a bare broker name answer (no "soy"/"somos" lead-in — the only other extraction path)
    was never captured. The identical combined question repeated verbatim instead of narrowing
    to just the still-missing period."""
    user_id = "user-regress-broker-bare-name"

    first = _post("I need to check my commissions.", user_id)
    assert "brokerage" in first["response"].lower()

    second = _post("Synthetic Brokerage Two", user_id, first["conversationId"])
    # Must narrow to ONLY the still-missing field, not repeat the full combined question.
    assert "period" in second["response"].lower()
    assert "name of your brokerage" not in second["response"].lower()


def test_ambiguous_customer_name_without_accent_still_resolves_and_disambiguates() -> None:
    """Defect: "Juan Perez" (typed without the accent — a very common, realistic input
    variance) failed to match the synthetic record "Juan Pérez" at all, so the ambiguous-entity
    disambiguation flow (multiple policies -> "la Hilux") could never even be reached."""
    user_id = "user-regress-accent-insensitive-entity"

    first = _post("I need to report a claim", user_id)
    second = _post("Juan Perez", user_id, first["conversationId"])
    assert second["agent"] == "ClaimsAgent"
    assert "could not find" not in second["response"].lower()
    assert "hilux" in second["response"].lower() or "sentra" in second["response"].lower()

    third = _post("la Hilux", user_id, second["conversationId"])
    assert "SYN-POL-1002" not in third["response"]  # internal id never leaked raw
    assert "what date did it occur" in third["response"].lower()


def test_opening_message_with_several_facts_reuses_the_location_without_re_asking() -> None:
    """Defect: an opening message packing several facts into one sentence never had its
    explicit "en <place>" location extracted, and separately, the extracted value used to sweep
    in an unrelated trailing clause ("...no hubo lesionados...") joined only by a comma."""
    user_id = "user-regress-opening-multi-fact-location"

    first = _post(
        "Quiero reportar un accidente. Mi poliza es SYN-POL-0001, chocamos ayer en Avenida "
        "Reforma, Ciudad de Mexico, no hubo lesionados ni terceros involucrados.",
        user_id,
    )
    assert first["agent"] == "ClaimsAgent"
    assert "dónde ocurrió" not in first["response"].lower()
    assert "ubicación" in first["response"] or "ubicaci" in first["response"].lower()

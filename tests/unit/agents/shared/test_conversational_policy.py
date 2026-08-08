"""Unit tests for src.agents.shared.conversational_policy (PBI-05-01)."""

from src.agents.shared.conversational_policy import loss_type_label, opening_acknowledgment


def test_loss_type_label_known_value() -> None:
    assert loss_type_label("water damage", "es-MX") == "una inundación"


def test_loss_type_label_unknown_value_falls_back_to_generic() -> None:
    assert loss_type_label("something-unrecognized", "es-MX") == "el incidente que reportas"


def test_loss_type_label_none_falls_back_to_generic() -> None:
    assert loss_type_label(None, "es-MX") == "el incidente que reportas"


def test_opening_acknowledgment_with_known_loss_type_includes_empathy_and_label() -> None:
    text = opening_acknowledgment(loss_type="water damage", language="es-MX")

    assert "Lamento lo ocurrido." in text
    assert "una inundación" in text


def test_opening_acknowledgment_without_loss_type_is_a_bare_lead_in() -> None:
    text = opening_acknowledgment(loss_type=None, language="es-MX")

    assert text == "Claro."


def test_opening_acknowledgment_english() -> None:
    text = opening_acknowledgment(loss_type="collision", language="en")

    assert "I'm sorry to hear that." in text
    assert "a collision" in text

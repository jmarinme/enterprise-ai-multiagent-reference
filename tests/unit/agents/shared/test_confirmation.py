"""Unit tests for the shared confirmation-understanding module (PBI-14-03 section 8)."""

import pytest

from src.agents.shared.confirmation import resolve_confirmation


@pytest.mark.parametrize(
    "message",
    [
        "si", "sí", "sip", "claro", "correcto", "confirmo", "adelante", "de acuerdo",
        "por supuesto", "afirmativo", "va", "yes", "yeah", "yep", "affirmative", "correct",
        "sure", "confirmed", "go ahead",
    ],
)
def test_deterministic_affirmative_words_resolve_true(message: str) -> None:
    assert resolve_confirmation(message) is True


@pytest.mark.parametrize(
    "message",
    [
        "no", "nop", "nel", "incorrecto", "cancela", "cancelar", "todavía no", "todavia no",
        "mejor no", "para nada", "nope", "negative", "none", "cancel",
    ],
)
def test_deterministic_negative_words_resolve_false(message: str) -> None:
    assert resolve_confirmation(message) is False


def test_negative_takes_precedence_when_both_markers_present() -> None:
    # A decline must never be silently read as a confirmation.
    assert resolve_confirmation("no, mejor no por ahora, va que va") is False


def test_case_and_punctuation_insensitive() -> None:
    assert resolve_confirmation("Sip!") is True
    assert resolve_confirmation("NO.") is False


def test_deterministic_fast_path_works_inside_a_longer_sentence() -> None:
    assert resolve_confirmation("Sí, adelante, regístralo por favor.") is True
    assert resolve_confirmation("No, todavía no estoy seguro.") is False


def test_falls_back_to_semantic_confirmation_when_deterministic_is_inconclusive() -> None:
    assert resolve_confirmation("tal vez más tarde", semantic_confirmation=True) is True
    assert resolve_confirmation("tal vez más tarde", semantic_confirmation=False) is False


def test_returns_none_when_both_deterministic_and_semantic_are_inconclusive() -> None:
    assert resolve_confirmation("tal vez más tarde") is None


def test_empty_message_falls_back_to_semantic_confirmation() -> None:
    assert resolve_confirmation("", semantic_confirmation=True) is True
    assert resolve_confirmation("") is None

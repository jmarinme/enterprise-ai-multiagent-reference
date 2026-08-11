"""Tests for src.agents.shared.summary (PBI-09-01 requirement 6 — conversation summarization)."""

from __future__ import annotations

from src.agents.shared.summary import build_progress_summary


def test_returns_remaining_prompt_unchanged_when_nothing_is_known_yet() -> None:
    assert build_progress_summary([], "es-MX", remaining_prompt="¿Cuál es tu nombre?") == (
        "¿Cuál es tu nombre?"
    )


def test_builds_the_checkmark_recap_in_spanish() -> None:
    result = build_progress_summary(
        ["póliza", "cliente", "fecha"], "es-MX", remaining_prompt="¿Dónde ocurrió?"
    )
    assert result == (
        "Hasta ahora tengo:\n✔ póliza\n✔ cliente\n✔ fecha\nSolo me falta: ¿Dónde ocurrió?"
    )


def test_builds_the_checkmark_recap_in_english() -> None:
    result = build_progress_summary(["policy", "customer"], "en", remaining_prompt="What date?")
    assert result == "So far I have:\n✔ policy\n✔ customer\nI just need: What date?"


def test_omits_the_remaining_line_when_no_remaining_prompt_given() -> None:
    result = build_progress_summary(["policy"], "en")
    assert result == "So far I have:\n✔ policy"

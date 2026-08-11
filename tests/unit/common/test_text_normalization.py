"""Unit tests for src.common.text_normalization (PBI-09-01 final validation)."""

from __future__ import annotations

from src.common.text_normalization import normalize_for_search


def test_strips_accents() -> None:
    assert normalize_for_search("Pérez") == "perez"


def test_lowercases() -> None:
    assert normalize_for_search("JUAN") == "juan"


def test_accented_and_unaccented_forms_compare_equal() -> None:
    assert normalize_for_search("México") == normalize_for_search("Mexico")


def test_leaves_plain_ascii_unchanged_besides_case() -> None:
    assert normalize_for_search("Synthetic Brokerage One") == "synthetic brokerage one"

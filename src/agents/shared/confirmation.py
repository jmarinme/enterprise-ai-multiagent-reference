"""Shared confirmation understanding (PBI-14-03 section 8) — one module Claims, Broker
Services, and Commercial Intake all call, instead of each duplicating (Claims/Broker) or
entirely lacking (Commercial, before this PBI) its own yes/no word list.

A deterministic normalization fast path recognizes the common Spanish/English affirmatives and
negatives up front — no LLM involved for the overwhelming majority of real replies. The
structured per-turn semantic interpretation's own `.confirmation` field (already produced by
the one repurposed LLM call every Agent makes — src.agents.shared.semantic_interpreter) is
consulted only when the fast path is inconclusive. The result is True/False/None — never a
literal-string match requirement (PBI-14-01's own finding: "sip" must be understood as an
affirmative, not just the exact word "si").
"""

from __future__ import annotations

import re

_AFFIRMATIVE_PHRASES: tuple[str, ...] = (
    "sí", "si", "sip", "claro", "correcto", "confirmo", "adelante", "de acuerdo",
    "por supuesto", "afirmativo", "va",
    "yes", "yeah", "yep", "affirmative", "correct", "sure", "confirmed", "go ahead",
)
_NEGATIVE_PHRASES: tuple[str, ...] = (
    "no", "nop", "nel", "incorrecto", "cancela", "cancelar", "todavía no", "todavia no",
    "mejor no", "para nada",
    "nope", "negative", "none", "cancel",
)

# Longest phrase first, so a multi-word phrase ("todavía no") is matched whole rather than a
# shorter phrase inside it ("no" alone) claiming the match first when both would otherwise fire.
_NEGATIVE_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in sorted(_NEGATIVE_PHRASES, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_AFFIRMATIVE_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in sorted(_AFFIRMATIVE_PHRASES, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def resolve_confirmation(message: str, *, semantic_confirmation: bool | None = None) -> bool | None:
    """True/False/None for a caller's reply to a yes/no question.

    Checks the deterministic negative word set before the affirmative one — a decline must
    never be silently read as a confirmation. Falls back to `semantic_confirmation` (the
    structured semantic interpretation's own `.confirmation` field) only when neither
    deterministic set matches anywhere in the message. Returns None when both are inconclusive
    — callers must re-prompt rather than guess (never silently treat a genuinely ambiguous
    reply as either a confirmation or a decline)."""
    normalized = message.strip()
    if not normalized:
        return semantic_confirmation

    if _NEGATIVE_PATTERN.search(normalized):
        return False
    if _AFFIRMATIVE_PATTERN.search(normalized):
        return True

    return semantic_confirmation

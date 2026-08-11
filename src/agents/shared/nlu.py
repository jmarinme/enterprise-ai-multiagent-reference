"""Shared, deterministic natural-language helpers for Spanish-first entity extraction
(PBI-05-01) — relative dates, commission-period expressions, natural name prefixes, and
phrase-level negation detection. Used by src.agents.claims.extraction and
src.agents.broker.extraction so both agents understand the same natural expressions the same
way, without duplicating the parsing rules.

Deliberately NOT LLM-based: MockLLMProvider is content-agnostic and cannot perform real NLU
(the same rationale documented in every extraction module since PBI-01-05), and CLAUDE.md's
architecture principle #2 ("the LLM is not the source of truth") applies to entity resolution
exactly as it does to any other business fact — a relative date or a selected policy must be
resolved the same way regardless of which LLMProvider is configured. Every function here is a
small, bounded, testable rule — not a general-purpose parser.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta

_RELATIVE_DATE_WORDS: dict[str, int] = {
    "hoy": 0,
    "today": 0,
    "ayer": -1,
    "yesterday": -1,
    "anoche": -1,
    "anteayer": -2,
    "antier": -2,
}

# Checked before _RELATIVE_DATE_WORDS below (PBI-09-01 requirement 4: "la semana pasada" is a
# common natural way to report an incident date but resolves to a *week* offset, not one of the
# single-day words above). "la semana pasada" has no single canonical day, so it resolves to
# exactly 7 days before `reference` — good enough for a synthetic demo's incident-date field,
# which only needs *a* plausible date, never a precise one down to the day of week.
_RELATIVE_WEEK_PATTERN = re.compile(r"\b(la semana pasada|last week)\b", re.IGNORECASE)

# "two days ago" / "hace 2 días" / "hace dos días" (PBI-09-01 final validation — English relative
# dates were entirely unsupported before this fix; only single Spanish day-words above existed).
# Small bounded word->number maps (1-10) are enough for this synthetic demo's incident-date field
# — never a general-purpose number parser.
_NUMBER_WORDS: dict[str, int] = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "un": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
}
_DAYS_AGO_EN_PATTERN = re.compile(
    r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+days?\s+ago\b", re.IGNORECASE
)
_DAYS_AGO_ES_PATTERN = re.compile(
    r"\bhace\s+(\d+|un|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\s+d[ií]as?\b",
    re.IGNORECASE,
)


def _parse_day_count(token: str) -> int | None:
    if token.isdigit():
        return int(token)
    return _NUMBER_WORDS.get(token.lower())

_MONTH_NAMES: dict[str, int] = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

_ORDINAL_QUARTER_WORDS: dict[str, int] = {
    "primer": 1, "primero": 1, "1er": 1,
    "segundo": 2, "2do": 2,
    "tercer": 3, "tercero": 3, "3er": 3,
    "cuarto": 4, "4to": 4,
}

_EXPLICIT_QUARTER_PATTERN = re.compile(r"\bQ([1-4])\s*[-/ ]?\s*(\d{4})\b", re.IGNORECASE)
_ISO_QUARTER_PATTERN = re.compile(r"\b(\d{4})\s*[-/ ]?\s*Q([1-4])\b", re.IGNORECASE)
_ORDINAL_QUARTER_PATTERN = re.compile(
    r"\b(primer|primero|1er|segundo|2do|tercer|tercero|3er|cuarto|4to)\s+trimestre"
    r"(?:\s+de\s+(\d{4}))?",
    re.IGNORECASE,
)
_THIS_QUARTER_PATTERN = re.compile(r"\beste\s+trimestre\b", re.IGNORECASE)
_MONTH_YEAR_PATTERN = re.compile(
    r"\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|"
    r"noviembre|diciembre)\s+(?:de\s+)?(\d{4})\b",
    re.IGNORECASE,
)

_NEGATION_MARKERS = ("no", "sin", "ni", "nunca", "jamás", "jamas", "ningún", "ningun")
# Deliberately excludes "hubo": "no hubo lesionados" contains "hubo" *after* the negation and
# *before* the keyword, which would otherwise look like an affirmation overriding the negation.
_AFFIRMATION_MARKERS = ("sí", "si", "presente", "presentes")


def resolve_relative_date(message: str, *, reference: date | None = None) -> str | None:
    """Resolve a bare relative-date word ("ayer", "anoche", "hoy", "anteayer") to an ISO
    "YYYY-MM-DD" string relative to `reference` (defaults to the server's current UTC date).
    Returns None if no relative-date word is present — callers should still try the existing
    absolute-date regex first, since an explicit date always takes precedence."""
    today = reference or datetime.now(UTC).date()
    lowered = message.lower()
    if _RELATIVE_WEEK_PATTERN.search(lowered):
        return (today - timedelta(days=7)).isoformat()
    days_ago_match = _DAYS_AGO_EN_PATTERN.search(lowered) or _DAYS_AGO_ES_PATTERN.search(lowered)
    if days_ago_match:
        count = _parse_day_count(days_ago_match.group(1))
        if count is not None:
            return (today - timedelta(days=count)).isoformat()
    for word, offset in _RELATIVE_DATE_WORDS.items():
        if re.search(rf"\b{word}\b", lowered):
            return (today + timedelta(days=offset)).isoformat()
    return None


def resolve_commission_period(message: str, *, reference: date | None = None) -> str | None:
    """Resolve a natural commission-period expression to a canonical "YYYY-Qn" string:
    "Q1 2026" / "2026-Q1" (explicit), "primer trimestre de 2026" / "segundo trimestre"
    (ordinal, year defaults to `reference`'s year when omitted), "este trimestre" (relative to
    `reference`), or "agosto 2026" (a month name maps to its calendar quarter). Returns None if
    no period expression is recognized."""
    today = reference or datetime.now(UTC).date()

    explicit = _EXPLICIT_QUARTER_PATTERN.search(message)
    if explicit:
        return f"{explicit.group(2)}-Q{explicit.group(1)}"

    iso = _ISO_QUARTER_PATTERN.search(message)
    if iso:
        return f"{iso.group(1)}-Q{iso.group(2)}"

    ordinal = _ORDINAL_QUARTER_PATTERN.search(message)
    if ordinal:
        quarter = _ORDINAL_QUARTER_WORDS[ordinal.group(1).lower()]
        year = ordinal.group(2) or str(today.year)
        return f"{year}-Q{quarter}"

    if _THIS_QUARTER_PATTERN.search(message):
        quarter = (today.month - 1) // 3 + 1
        return f"{today.year}-Q{quarter}"

    month_year = _MONTH_YEAR_PATTERN.search(message)
    if month_year:
        month_number = _MONTH_NAMES[month_year.group(1).lower()]
        quarter = (month_number - 1) // 3 + 1
        return f"{month_year.group(2)}-Q{quarter}"

    return None


def strip_natural_prefix(message: str, prefixes: tuple[str, ...]) -> str:
    """Strip one leading natural-language lead-in phrase ("mi nombre es ", "soy ", "somos ")
    from message, case-insensitively, so only the actual entity remains — "mi nombre es Juan
    Pérez" becomes "Juan Pérez", not the whole phrase. Returns message unchanged (just
    stripped of surrounding whitespace/punctuation) if no prefix matches."""
    normalized = message.strip()
    lowered = normalized.lower()
    for prefix in sorted(prefixes, key=len, reverse=True):
        if lowered.startswith(prefix):
            return normalized[len(prefix) :].strip(" ,.:;-")
    return normalized.strip(" ,.:;-")


def detect_negated_topic(message: str, topic_keywords: tuple[str, ...]) -> bool | None:
    """Search message for any of topic_keywords (substring, case-insensitive). Returns:
    - None if no keyword is present at all (topic not mentioned this message);
    - False if the nearest keyword occurrence is preceded anywhere earlier in the message by a
      negation marker ("no", "sin", "ni", ...) with no affirmation marker in between;
    - True otherwise (the topic is mentioned and not negated).

    Deliberately message-wide rather than clause-scoped: "no hubo lesionados ni terceros"
    negates "terceros" correctly even though the literal word "no" appears before "lesionados",
    not immediately before "terceros" — in Spanish, "ni" always continues a prior negation
    regardless of distance, so treating any earlier negation/"ni" as still in force is a safe
    simplification for this bounded, non-adversarial demo-conversation use case."""
    lowered = message.lower()
    keyword_index = -1
    for keyword in topic_keywords:
        found = lowered.find(keyword)
        if found != -1:
            keyword_index = found
            break
    if keyword_index == -1:
        return None

    preceding = lowered[:keyword_index]
    last_negation = max((preceding.rfind(marker) for marker in _NEGATION_MARKERS), default=-1)
    if last_negation == -1:
        return True

    last_affirmation = max(
        (preceding.rfind(marker) for marker in _AFFIRMATION_MARKERS), default=-1
    )
    # An affirmation marker occurring strictly after the last negation marker overrides it
    # ("no hubo lesionados, sí hubo daños materiales" — contrived, but the rule must not
    # silently flip on a later, unrelated "sí"). Otherwise the negation still governs.
    return last_affirmation > last_negation

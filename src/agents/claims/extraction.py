"""Deterministic field extraction for claims intake (PBI-01-05).

MockLLMProvider is intentionally content-agnostic (its output depends only on message length,
never meaning), so it cannot perform real NLU. Every business fact the Agent relies on must
therefore come from regex/keyword rules here, never from LLM output — this is what keeps
ClaimsAgent's behavior identical regardless of which LLMProvider is configured.
"""

from __future__ import annotations

import re

from src.agents.claims.state import ClaimsIntakeState

_POLICY_NUMBER_PATTERN = re.compile(r"\b([A-Za-z]{2,4}-[A-Za-z]{2,4}-\d{3,6})\b")
_DATE_PATTERN = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_TIME_PATTERN = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\s?(am|pm|AM|PM)?\b")
_EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
# 3-3-4 digit grouping (optionally with a country code) so a YYYY-MM-DD date (4-2-2 grouping)
# is never mistaken for a phone number.
_PHONE_PATTERN = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")

_YES_WORDS = {"yes", "yeah", "yep", "affirmative", "correct", "si", "sí"}
_NO_WORDS = {"no", "nope", "negative", "none"}

_LOSS_TYPE_KEYWORDS: dict[str, str] = {
    "collision": "collision",
    "crash": "collision",
    "theft": "theft",
    "stolen": "theft",
    "fire": "fire",
    "flood": "water damage",
    "water": "water damage",
    "vandalism": "vandalism",
    "storm": "weather",
    "weather": "weather",
    "hail": "weather",
}

# Fields genuinely free-form enough that, absent any structured match, the raw answer to the
# most recently asked question is attributed to them. Fields with their own regex/keyword
# extraction (policy_number, event_date, event_time, contact_phone, contact_email,
# injuries_reported, third_parties_involved) never fall back this way, so an unparseable
# answer to a structured question (e.g. a malformed date) correctly leaves the field missing
# and re-prompts, rather than silently accepting bad data.
_FREE_TEXT_FALLBACK_FIELDS = {"event_location", "loss_description", "contact_name", "loss_type"}
_YES_NO_FIELDS = {"injuries_reported", "third_parties_involved"}


def extract_fields(message: str, state: ClaimsIntakeState) -> ClaimsIntakeState:
    """Return a copy of state with any recognizable fields from message filled in."""
    updated = state.model_copy()
    normalized = message.strip()
    matched_structured_field = False

    policy_match = _POLICY_NUMBER_PATTERN.search(normalized)
    if policy_match:
        # Always refreshed (not gated on being previously unset): after a "policy not found"
        # notice, the user is expected to supply a corrected number in reply.
        updated.policy_number = policy_match.group(1).upper()
        matched_structured_field = True

    if updated.event_date is None:
        date_match = _DATE_PATTERN.search(normalized)
        if date_match:
            updated.event_date = date_match.group(1)
            matched_structured_field = True

    if updated.event_time is None:
        time_match = _TIME_PATTERN.search(normalized)
        if time_match:
            updated.event_time = time_match.group(0).strip()
            matched_structured_field = True

    if updated.contact_email is None:
        email_match = _EMAIL_PATTERN.search(normalized)
        if email_match:
            updated.contact_email = email_match.group(0)
            matched_structured_field = True

    if updated.contact_phone is None:
        phone_match = _PHONE_PATTERN.search(normalized)
        if phone_match:
            updated.contact_phone = phone_match.group(0).strip()
            matched_structured_field = True

    if updated.loss_type is None:
        lowered = normalized.lower()
        for keyword, canonical in _LOSS_TYPE_KEYWORDS.items():
            if keyword in lowered:
                updated.loss_type = canonical
                matched_structured_field = True
                break

    if state.last_asked_field in _YES_NO_FIELDS and getattr(updated, state.last_asked_field) is None:
        first_word = normalized.lower().split()[0].strip(",.!?") if normalized else ""
        if first_word in _YES_WORDS:
            setattr(updated, state.last_asked_field, True)
            matched_structured_field = True
        elif first_word in _NO_WORDS:
            setattr(updated, state.last_asked_field, False)
            matched_structured_field = True

    if (
        not matched_structured_field
        and state.last_asked_field in _FREE_TEXT_FALLBACK_FIELDS
        and getattr(updated, state.last_asked_field) is None
        and normalized
    ):
        setattr(updated, state.last_asked_field, normalized)

    return updated

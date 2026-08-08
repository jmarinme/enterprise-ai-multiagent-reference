"""Deterministic field extraction for claims intake (PBI-01-05, extended by PBI-04-04 with
customer-name capture and plain-language policy-candidate selection).

MockLLMProvider is intentionally content-agnostic (its output depends only on message length,
never meaning), so it cannot perform real NLU. Every business fact the Agent relies on must
therefore come from regex/keyword rules here, never from LLM output — this is what keeps
ClaimsAgent's behavior identical regardless of which LLMProvider is configured.
"""

from __future__ import annotations

import re

from src.agents.claims.state import ClaimsIntakeState, PolicyCandidate

_POLICY_NUMBER_PATTERN = re.compile(r"\b([A-Za-z]{2,4}-[A-Za-z]{2,4}-\d{3,6})\b")
_DATE_PATTERN = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_TIME_PATTERN = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\s?(am|pm|AM|PM)?\b")
_EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
# 3-3-4 digit grouping (optionally with a country code) so a YYYY-MM-DD date (4-2-2 grouping)
# is never mistaken for a phone number.
_PHONE_PATTERN = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")

_YES_WORDS = {"yes", "yeah", "yep", "affirmative", "correct", "si", "sí", "claro", "correcto"}
_NO_WORDS = {"no", "nope", "negative", "none", "para nada"}

_LOSS_TYPE_KEYWORDS: dict[str, str] = {
    "collision": "collision",
    "crash": "collision",
    "colisión": "collision",
    "colision": "collision",
    "choque": "collision",
    "theft": "theft",
    "stolen": "theft",
    "robo": "theft",
    "robaron": "theft",
    "fire": "fire",
    "incendio": "fire",
    "flood": "water damage",
    "water": "water damage",
    "inundación": "water damage",
    "inundacion": "water damage",
    "agua": "water damage",
    "vandalism": "vandalism",
    "vandalismo": "vandalism",
    "storm": "weather",
    "weather": "weather",
    "hail": "weather",
    "clima": "weather",
    "granizo": "weather",
}

# Fields genuinely free-form enough that, absent any structured match, the raw answer to the
# most recently asked question is attributed to them. Fields with their own regex/keyword
# extraction (policy_number, event_date, event_time, contact_phone, contact_email,
# injuries_reported, third_parties_involved) never fall back this way, so an unparseable
# answer to a structured question (e.g. a malformed date) correctly leaves the field missing
# and re-prompts, rather than silently accepting bad data.
_FREE_TEXT_FALLBACK_FIELDS = {"event_location", "loss_description", "customer_name", "loss_type"}
_YES_NO_FIELDS = {"injuries_reported", "third_parties_involved", "confirmed"}

_LOCATION_CONNECTOR_PATTERN = re.compile(r"^(en|at|in)\s+", re.IGNORECASE)

_ORDINAL_WORDS: dict[str, int] = {
    "primera": 0, "primero": 0, "first": 0, "1": 0, "uno": 0,
    "segunda": 1, "segundo": 1, "second": 1, "2": 1, "dos": 1,
    "tercera": 2, "tercero": 2, "third": 2, "3": 2, "tres": 2,
}


def extract_fields(message: str, state: ClaimsIntakeState) -> ClaimsIntakeState:
    """Return a copy of state with any recognizable fields from message filled in."""
    updated = state.model_copy()
    normalized = message.strip()
    matched_structured_field = False
    # Spans consumed by a structured match, so the event_location group-fallback below can
    # strip them out rather than treating the whole message (date and all) as the location.
    consumed_spans: list[tuple[int, int]] = []

    policy_match = _POLICY_NUMBER_PATTERN.search(normalized)
    if policy_match:
        # Always refreshed (not gated on being previously unset): after a "policy not found"
        # notice, the user is expected to supply a corrected number in reply. A direct policy
        # number always short-circuits customer discovery (see workflow.py).
        updated.policy_number = policy_match.group(1).upper()
        matched_structured_field = True

    if updated.event_date is None:
        date_match = _DATE_PATTERN.search(normalized)
        if date_match:
            updated.event_date = date_match.group(1)
            matched_structured_field = True
            consumed_spans.append(date_match.span())

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
            keyword_index = lowered.find(keyword)
            if keyword_index != -1:
                updated.loss_type = canonical
                matched_structured_field = True
                consumed_spans.append((keyword_index, keyword_index + len(keyword)))
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

    # A combined question (e.g. "what date, where, and what type of loss?") can leave
    # event_location unanswered even though the caller *did* answer it in the same message —
    # last_asked_field only ever names one field (event_date, here), so the plain single-field
    # fallback above never fires for event_location. Recover it by stripping whatever
    # structured spans were just consumed (the date, a matched loss-type keyword) and treating
    # any meaningful remainder as the location, but only when event_location was genuinely part
    # of the question just asked and nothing already claimed it as free text.
    if (
        updated.event_location is None
        and "event_location" in state.last_asked_group
        and state.last_asked_field != "event_location"
    ):
        remainder = normalized
        for start, end in sorted(consumed_spans, reverse=True):
            remainder = remainder[:start] + remainder[end:]
        remainder = remainder.strip(" ,.;:-")
        # A caller answering "where?" naturally leads with a connector word ("en Avenida
        # Reforma", "in Reforma Avenue") that would otherwise double up with the confirmation
        # summary's own "en {event_location}"/"at {event_location}" phrasing.
        remainder = _LOCATION_CONNECTOR_PATTERN.sub("", remainder, count=1).strip(" ,.;:-")
        if remainder:
            updated.event_location = remainder

    return updated


def resolve_selection(message: str, candidates: list[PolicyCandidate]) -> PolicyCandidate | None:
    """Resolve a plain-language policy selection ("la primera", "the second one", "la Hilux",
    "la de auto") against a short list of candidates surfaced by customer_lookup. Returns None
    if the message does not clearly identify exactly one candidate — the caller re-prompts
    rather than guessing."""
    lowered = message.strip().lower()
    if not lowered or not candidates:
        return None

    for word, index in _ORDINAL_WORDS.items():
        if (word in lowered.split() or lowered == word) and 0 <= index < len(candidates):
            return candidates[index]

    # A candidate matches if any word of its own vehicle description (e.g. "hilux" from "Toyota
    # Hilux 2021") appears as a whole word in the caller's short message — not the other way
    # around, since the caller's message ("la Hilux") is normally much shorter than the full
    # description it's referring to and could never contain it as a substring.
    message_words = set(lowered.split())
    vehicle_matches = [
        candidate
        for candidate in candidates
        if candidate.vehicle_description
        and message_words & set(candidate.vehicle_description.lower().split())
    ]
    if len(vehicle_matches) == 1:
        return vehicle_matches[0]

    line_of_business_matches = [
        candidate for candidate in candidates if candidate.line_of_business.lower() in lowered
    ]
    if len(line_of_business_matches) == 1:
        return line_of_business_matches[0]

    policy_number_matches = [
        candidate for candidate in candidates if candidate.policy_number.lower() in lowered
    ]
    if len(policy_number_matches) == 1:
        return policy_number_matches[0]

    return None

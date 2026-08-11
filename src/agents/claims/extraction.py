"""Deterministic field extraction for claims intake (PBI-01-05, extended by PBI-04-04 with
customer-name capture and plain-language policy-candidate selection, and by PBI-05-01 with
natural-language prefixes, relative dates, phrase-level negation for multi-fact turns, and
line-of-business-specific fields).

MockLLMProvider is intentionally content-agnostic (its output depends only on message length,
never meaning), so it cannot perform real NLU. Every business fact the Agent relies on must
therefore come from regex/keyword rules here, never from LLM output — this is what keeps
ClaimsAgent's behavior identical regardless of which LLMProvider is configured.
"""

from __future__ import annotations

import re

from src.agents.claims.state import ClaimsIntakeState, PolicyCandidate
from src.agents.shared.nlu import (
    detect_negated_topic,
    resolve_relative_date,
    strip_natural_prefix,
)

_POLICY_NUMBER_PATTERN = re.compile(r"\b([A-Za-z]{2,4}-[A-Za-z]{2,4}-\d{3,6})\b")
_DATE_PATTERN = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_TIME_PATTERN = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\s?(am|pm|AM|PM)?\b")
_EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
# 3-3-4 digit grouping (optionally with a country code) so a YYYY-MM-DD date (4-2-2 grouping)
# is never mistaken for a phone number.
_PHONE_PATTERN = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")

_YES_WORDS = {"yes", "yeah", "yep", "affirmative", "correct", "si", "sí", "claro", "correcto"}
_NO_WORDS = {"no", "nope", "negative", "none", "para nada"}

# Stems (not whole words) where a single stem safely catches every conjugation/inflection this
# demo needs ("choc" -> choque/chocaron/chocó/chocando; "inund" -> inundación/inundó/inunda;
# "rob" -> robo/robaron/robó/robada; "graniz" -> granizo/granizada) — deliberately not full
# words, unlike the rest of the map, since matching is already a substring search.
_LOSS_TYPE_KEYWORDS: dict[str, str] = {
    "collision": "collision",
    "crash": "collision",
    "colisión": "collision",
    "colision": "collision",
    "choc": "collision",
    "theft": "theft",
    "stolen": "theft",
    "rob": "theft",
    "fire": "fire",
    "incendio": "fire",
    "flood": "water damage",
    "water": "water damage",
    "inund": "water damage",
    "agua": "water damage",
    "vandalism": "vandalism",
    "vandalismo": "vandalism",
    "storm": "weather",
    "weather": "weather",
    "hail": "weather",
    "clima": "weather",
    "graniz": "weather",
    "llov": "weather",
    "lluvia": "weather",
    "glass": "glass",
    "cristal": "glass",
    "parabrisas": "glass",
    "vidrio": "glass",
}

# Fields genuinely free-form enough that, absent any structured match, the raw answer to the
# most recently asked question is attributed to them. Fields with their own regex/keyword
# extraction (policy_number, event_date, event_time, contact_phone, contact_email,
# injuries_reported, third_parties_involved) never fall back this way, so an unparseable
# answer to a structured question (e.g. a malformed date) correctly leaves the field missing
# and re-prompts, rather than silently accepting bad data.
_FREE_TEXT_FALLBACK_FIELDS = {"event_location", "loss_description", "customer_name", "loss_type"}
_YES_NO_FIELDS = {
    "injuries_reported", "third_parties_involved", "confirmed",
    # A caller may answer "¿El vehículo todavía puede circular?"/"¿Pueden permanecer en la
    # propiedad?" with a bare "sí"/"no" instead of a full explanatory phrase — the phrase-level
    # _detect_bool_phrase check above runs first and takes precedence when a richer phrase is
    # used; this is the fallback for a plain yes/no reply.
    "vehicle_drivable", "property_habitable",
}

# "en Reforma", "at the mall" — captures everything after the connector up to the end of that
# clause (a period, or the end of the message) so a rich multi-clause message ("...en Reforma.
# Yo manejaba, no hubo lesionados...") does not spill the *next* sentence into the location, while
# "2026-08-07, en Avenida Reforma, Ciudad de Mexico" (commas belong to the location itself, no
# following sentence) still captures the whole remainder.
_LOCATION_PHRASE_PATTERN = re.compile(r"\b(?:en|at)\s+([^.]+)", re.IGNORECASE)

# PBI-09-01 final validation: "en"/"at" also start several extremely common discourse idioms
# that are not locations at all ("en realidad" = "actually", "en fin" = "anyway") — a live test
# surfaced "En realidad, volvamos a mi accidente." (a domain-switch-back message) silently
# corrupting event_location with "realidad, volvamos a mi accidente" once opportunistic
# extraction was made unconditional. Small, bounded denylist, same philosophy as every other
# keyword map in this module — not a general discourse-marker detector.
_NON_LOCATION_PREPOSITION_FOLLOWERS = (
    "realidad", "efecto", "fin", "cambio", "general", "serio", "resumen", "conclusión", "conclusion",
)

# PBI-09-01 final validation: cuts a captured location off right before a comma-joined,
# negation-led independent clause ("...Ciudad de Mexico, no hubo lesionados...") — see
# _extract_location_phrase's own docstring.
_LOCATION_TRAILING_CLAUSE_PATTERN = re.compile(r",\s*(?:no|sin|ni)\b", re.IGNORECASE)

# "mi nombre es Juan Pérez" / "soy Juan Pérez" / "me llamo Juan Pérez" -> "Juan Pérez" (PBI-05-01
# requirement 3) — checked before customer_name ever falls back to the whole raw message.
_NAME_PREFIXES: tuple[str, ...] = ("mi nombre es", "me llamo", "soy")

_INJURY_TOPIC_KEYWORDS = ("lesionad", "herid")
_THIRD_PARTY_TOPIC_KEYWORDS = ("tercero", "third part")

_VEHICLE_DRIVABLE_FALSE_PHRASES = (
    "no puede circular", "ya no circula", "no circula", "quedó inservible",
    "no es funcional", "no está en condiciones de circular",
)
_VEHICLE_DRIVABLE_TRUE_PHRASES = (
    "puede circular", "sigue circulando", "todavía circula", "es funcional",
)
_HABITABLE_FALSE_PHRASES = (
    "tuvimos que salir", "no es habitable", "no podemos permanecer", "tuvimos que evacuar",
    "no podemos quedarnos", "tuvimos que dejar la casa",
)
_HABITABLE_TRUE_PHRASES = (
    "podemos permanecer", "seguimos viviendo", "es habitable", "podemos quedarnos",
)

_ORDINAL_WORDS: dict[str, int] = {
    "primera": 0, "primero": 0, "first": 0, "1": 0, "uno": 0,
    "segunda": 1, "segundo": 1, "second": 1, "2": 1, "dos": 1,
    "tercera": 2, "tercero": 2, "third": 2, "3": 2, "tres": 2,
}

# Natural-language synonyms for a policy's line_of_business, used only to disambiguate a
# selection among a customer's own policies ("la de auto", "la de hogar") — never a source of
# the authoritative line_of_business itself, which always comes from the Tool result.
_LINE_OF_BUSINESS_SYNONYMS: dict[str, tuple[str, ...]] = {
    "auto": ("auto", "carro", "coche", "vehículo", "vehiculo"),
    "property": ("hogar", "casa", "vivienda", "propiedad", "property"),
}


def _detect_bool_phrase(
    lowered: str, true_phrases: tuple[str, ...], false_phrases: tuple[str, ...]
) -> bool | None:
    """False-phrases are checked first because some true-phrases are substrings of their
    negated counterpart ("puede circular" is contained in "no puede circular")."""
    if any(phrase in lowered for phrase in false_phrases):
        return False
    if any(phrase in lowered for phrase in true_phrases):
        return True
    return None


def extract_fields(message: str, state: ClaimsIntakeState) -> ClaimsIntakeState:
    """Return a copy of state with any recognizable fields from message filled in."""
    updated = state.model_copy()
    normalized = message.strip()
    lowered = normalized.lower()
    matched_structured_field = False

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
        else:
            relative_date = resolve_relative_date(normalized)
            if relative_date:
                updated.event_date = relative_date
                matched_structured_field = True

    if updated.event_time is None:
        time_match = _TIME_PATTERN.search(normalized)
        if time_match:
            updated.event_time = time_match.group(0).strip()
            matched_structured_field = True

    # PBI-09-01 final validation: previously only ever attempted when a prior question had
    # specifically been about location (last_asked_field/last_asked_group) — an opening message
    # that packs several facts into one sentence ("...chocamos ayer en Avenida Reforma, Ciudad
    # de Mexico...") never got its explicit "en <place>" location extracted at all, so a caller
    # who volunteered it up front was asked for it again anyway. Safe to attempt unconditionally
    # like policy_number/event_date/loss_type above: it only ever fires on an explicit "en"/"at"
    # marker (see _extract_location_phrase), never a blind guess.
    if updated.event_location is None:
        opportunistic_location = _extract_location_phrase(normalized)
        if opportunistic_location:
            updated.event_location = opportunistic_location
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
        for keyword, canonical in _LOSS_TYPE_KEYWORDS.items():
            keyword_index = lowered.find(keyword)
            if keyword_index != -1:
                updated.loss_type = canonical
                matched_structured_field = True
                break

    # Deliberately does NOT set matched_structured_field for these four: they are narrative
    # asides embedded in a longer message ("...no hubo lesionados y todavía podemos permanecer
    # en la casa"), never a competing interpretation of whatever free-text field
    # (event_location/loss_description/customer_name) is currently being asked about — unlike
    # policy_number/event_date/contact_email/contact_phone/loss_type above, which genuinely can
    # be mistaken for "the whole answer" to a different question (see
    # test_free_text_fallback_is_skipped_when_a_structured_field_matched_instead). Found via
    # live DEV validation: gating the simple fallback on these caused a rich Property message
    # ("Se dañaron los muebles..., no hubo lesionados y todavía podemos permanecer en la casa.")
    # to silently drop its own answer to "¿Dónde ocurrió el incidente?" just because injuries
    # was also mentioned in the same message.
    if updated.injuries_reported is None:
        injuries = detect_negated_topic(normalized, _INJURY_TOPIC_KEYWORDS)
        if injuries is not None:
            updated.injuries_reported = injuries

    if updated.third_parties_involved is None:
        third_parties = detect_negated_topic(normalized, _THIRD_PARTY_TOPIC_KEYWORDS)
        if third_parties is not None:
            updated.third_parties_involved = third_parties

    if updated.vehicle_drivable is None:
        drivable = _detect_bool_phrase(
            lowered, _VEHICLE_DRIVABLE_TRUE_PHRASES, _VEHICLE_DRIVABLE_FALSE_PHRASES
        )
        if drivable is not None:
            updated.vehicle_drivable = drivable

    if updated.property_habitable is None:
        habitable = _detect_bool_phrase(
            lowered, _HABITABLE_TRUE_PHRASES, _HABITABLE_FALSE_PHRASES
        )
        if habitable is not None:
            updated.property_habitable = habitable

    # A bare "no" answering the combined injuries+third-parties question, with no field-specific
    # keyword at all ("no, solo se dañaron los muebles"), safely implies both are negative —
    # this is the one case a genuinely ambiguous "no" is safe to expand to two fields, because
    # the question that prompted it was specifically about both together. Checked BEFORE the
    # single-field yes/no fallback below (PBI-09-01 final validation: this used to run second,
    # so the single-field check always claimed injuries_reported first and left
    # third_parties_involved to redundantly re-ask on its own — exactly the "one answer should
    # unlock both" defect requirement 5/9 exist to prevent).
    if (
        set(state.last_asked_group) == {"injuries_reported", "third_parties_involved"}
        and updated.injuries_reported is None
        and updated.third_parties_involved is None
        and lowered.split(",")[0].strip().split()[:1] == ["no"]
    ):
        updated.injuries_reported = False
        updated.third_parties_involved = False
        matched_structured_field = True

    if state.last_asked_field in _YES_NO_FIELDS and getattr(updated, state.last_asked_field) is None:
        first_word = lowered.split()[0].strip(",.!?") if lowered else ""
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
        value = normalized
        if state.last_asked_field == "customer_name":
            value = strip_natural_prefix(normalized, _NAME_PREFIXES)
        elif state.last_asked_field == "event_location":
            # Even a directly-asked "¿Dónde ocurrió el incidente?" can receive a rich,
            # multi-clause reply that also answers other fields (loss description, injuries,
            # habitability) in the same message — found via live DEV validation. Prefer the
            # same explicit "en <place>"/"at <place>" extraction the grouped-question recovery
            # uses; only a bare place name with no marker ("In my driveway") falls back to the
            # whole trimmed message.
            value = _extract_location_phrase(normalized) or normalized
        setattr(updated, state.last_asked_field, value)

    # A combined question (e.g. "what date, where, and what type of loss?") can leave
    # event_location unanswered even though the caller *did* answer it in the same message —
    # last_asked_field only ever names one field (event_date, here), so the plain single-field
    # fallback above never fires for event_location. Recover it by searching for an explicit
    # "en <place>"/"at <place>" marker (never a blind "whatever's left over" strip — a richer
    # multi-clause message, e.g. one that also states the loss type and injuries/third-parties
    # in the same turn, made an earlier consumed-span-stripping approach garble badly), only
    # when event_location was genuinely part of the question just asked and nothing already
    # claimed it as free text.
    if (
        updated.event_location is None
        and "event_location" in state.last_asked_group
        and state.last_asked_field != "event_location"
    ):
        location = _extract_location_phrase(normalized)
        if location:
            updated.event_location = location

    return updated


def _extract_location_phrase(message: str) -> str | None:
    """Search each sentence-like clause (split on ". ") for an "en <place>"/"at <place>"
    marker, returning the text after it up to the end of that same clause — so a location
    naturally containing a comma ("Avenida Reforma, Ciudad de Mexico") is captured whole, while
    a location clause followed by an unrelated sentence ("...en Reforma. Yo manejaba...") does
    not spill that next sentence into the location."""
    for clause in re.split(r"\.\s*", message):
        match = _LOCATION_PHRASE_PATTERN.search(clause)
        if match:
            candidate = match.group(1).strip(" ,.;:-")
            first_word = candidate.split(" ", 1)[0].strip(" ,.;:-").lower() if candidate else ""
            if first_word in _NON_LOCATION_PREPOSITION_FOLLOWERS:
                continue
            # PBI-09-01 final validation: a rich opening message ("...en Avenida Reforma, Ciudad
            # de Mexico, no hubo lesionados ni terceros...") has no period separating the
            # address from the next, unrelated clause — only a comma — so without this the
            # negation clause was swept into the location verbatim. A real address never
            # contains ", no "/ ", sin "/ ", ni " (this codebase's own existing negation
            # markers, src.agents.shared.nlu), so cutting there is safe.
            trailing_clause = _LOCATION_TRAILING_CLAUSE_PATTERN.search(candidate)
            if trailing_clause:
                candidate = candidate[: trailing_clause.start()].strip(" ,.;:-")
            if candidate:
                return candidate
    return None


def resolve_selection(message: str, candidates: list[PolicyCandidate]) -> PolicyCandidate | None:
    """Resolve a plain-language policy selection ("la primera", "the second one", "la Hilux",
    "la de auto", "la de hogar") against a short list of candidates surfaced by
    customer_lookup. Returns None if the message does not clearly identify exactly one
    candidate — the caller re-prompts rather than guessing."""
    lowered = message.strip().lower()
    if not lowered or not candidates:
        return None

    # Punctuation-stripped per word (not just the whole message) so a trailing period/comma on
    # the selected word itself ("La Hilux.", "la segunda,") never breaks an otherwise-exact
    # word match.
    words = [word.strip(" ,.;:!?") for word in lowered.split()]

    for word, index in _ORDINAL_WORDS.items():
        if (word in words or lowered.strip(" ,.;:!?") == word) and 0 <= index < len(candidates):
            return candidates[index]

    # A candidate matches if any word of its own vehicle/property description (e.g. "hilux"
    # from "Toyota Hilux 2021") appears as a whole word in the caller's short message — not the
    # other way around, since the caller's message ("la Hilux") is normally much shorter than
    # the full description it's referring to and could never contain it as a substring.
    message_words = set(words)
    description_matches = [
        candidate
        for candidate in candidates
        if (candidate.vehicle_description or candidate.property_description)
        and message_words
        & set((candidate.vehicle_description or candidate.property_description or "").lower().split())
    ]
    if len(description_matches) == 1:
        return description_matches[0]

    line_of_business_matches = [
        candidate
        for candidate in candidates
        if candidate.line_of_business.lower() in lowered
        or any(
            synonym in lowered
            for synonym in _LINE_OF_BUSINESS_SYNONYMS.get(candidate.line_of_business.lower(), ())
        )
    ]
    if len(line_of_business_matches) == 1:
        return line_of_business_matches[0]

    policy_number_matches = [
        candidate for candidate in candidates if candidate.policy_number.lower() in lowered
    ]
    if len(policy_number_matches) == 1:
        return policy_number_matches[0]

    return None

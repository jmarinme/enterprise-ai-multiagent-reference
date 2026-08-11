"""Unit tests for deterministic claims-intake field extraction. No LLM involved — every case
here must be resolvable by regex/keyword rules alone (MockLLMProvider cannot do real NLU).
"""

from src.agents.claims.extraction import extract_fields, resolve_selection
from src.agents.claims.state import ClaimsIntakeState, PolicyCandidate


def test_extracts_policy_number_in_either_case() -> None:
    state = extract_fields("my policy is syn-pol-0001", ClaimsIntakeState())

    assert state.policy_number == "SYN-POL-0001"


def test_policy_number_is_refreshed_even_if_already_set() -> None:
    state = ClaimsIntakeState(policy_number="SYN-POL-9999")

    updated = extract_fields("actually it's SYN-POL-0001", state)

    assert updated.policy_number == "SYN-POL-0001"


def test_validated_policy_number_is_never_overwritten_by_an_incidental_match() -> None:
    """Functional defect fix: once a policy number has actually been confirmed by a real Tool
    call (policy_validated=True), it must be immutable for the rest of the conversation — an
    unrelated reference number mentioned in passing in a later free-form reply (e.g. "el número
    de referencia del taller es AB-CD-123") must never silently overwrite the canonical,
    already-validated value. Contrast with test_policy_number_is_refreshed_even_if_already_set
    above, where the state is *not yet* validated and a correction is expected to be accepted."""
    state = ClaimsIntakeState(
        policy_number="SYN-POL-0001",
        policy_validated=True,
        last_asked_field="injuries_reported",
        last_asked_group=["injuries_reported", "third_parties_involved"],
    )

    updated = extract_fields("El número de referencia del taller es AB-CD-123.", state)

    assert updated.policy_number == "SYN-POL-0001"


def test_bare_no_after_policy_validation_preserves_the_canonical_policy_number() -> None:
    """Direct regression for the reported scenario: after the policy is validated, answering
    the combined injuries+third-parties question must never touch policy_number, regardless of
    that this exact message does not itself contain a policy-shaped token — this guards the
    fix's gating logic (state.policy_validated), not just the regex match itself."""
    state = ClaimsIntakeState(
        policy_number="SYN-POL-0001",
        policy_validated=True,
        last_asked_field="injuries_reported",
        last_asked_group=["injuries_reported", "third_parties_involved"],
    )

    updated = extract_fields("No hubo personas lesionadas ni terceros involucrados.", state)

    assert updated.policy_number == "SYN-POL-0001"
    assert updated.injuries_reported is False
    assert updated.third_parties_involved is False


def test_extracts_event_date_in_iso_format() -> None:
    state = extract_fields("it happened on 2026-08-01", ClaimsIntakeState())

    assert state.event_date == "2026-08-01"


def test_a_date_is_never_mistaken_for_a_phone_number() -> None:
    state = extract_fields("2026-08-01", ClaimsIntakeState())

    assert state.event_date == "2026-08-01"
    assert state.contact_phone is None


def test_extracts_phone_number() -> None:
    state = extract_fields("you can reach me at 555-123-4567", ClaimsIntakeState())

    assert state.contact_phone is not None
    assert "555" in state.contact_phone


def test_extracts_email() -> None:
    state = extract_fields("email me at jane@example.com please", ClaimsIntakeState())

    assert state.contact_email == "jane@example.com"


def test_extracts_loss_type_from_keyword() -> None:
    state = extract_fields("there was a collision on the highway", ClaimsIntakeState())

    assert state.loss_type == "collision"


def test_extracts_weather_loss_type_from_llovio() -> None:
    """PBI-09-01 requirement 4's own example: "llovió" must be recognized as a weather-loss
    signal, same as the existing "clima"/"granizo" keywords."""
    state = extract_fields("llovió mucho y se inundó mi casa", ClaimsIntakeState())

    assert state.loss_type == "water damage"  # "inund" is checked before "llov" in the map


def test_extracts_weather_loss_type_from_lluvia_alone() -> None:
    state = extract_fields("hubo una lluvia muy fuerte anoche", ClaimsIntakeState())

    assert state.loss_type == "weather"


def test_yes_no_answer_is_only_interpreted_for_the_last_asked_yes_no_field() -> None:
    state = ClaimsIntakeState(last_asked_field="injuries_reported")

    updated = extract_fields("no", state)

    assert updated.injuries_reported is False
    assert updated.third_parties_involved is None


def test_yes_answer_sets_the_field_true() -> None:
    state = ClaimsIntakeState(last_asked_field="third_parties_involved")

    updated = extract_fields("yes, another driver", state)

    assert updated.third_parties_involved is True


def test_bare_no_answers_both_injuries_and_third_parties_from_the_combined_question() -> None:
    """PBI-09-01 final validation: a live conversational test found that a bare "no" answering
    the combined injuries+third-parties question only ever resolved injuries_reported — the
    single-field yes/no fallback ran before the "combo" check and always claimed the field
    first, forcing a redundant second "were any third parties involved?" question the caller
    had already effectively answered. Requirement 5/9: never ask twice what one answer covers."""
    state = ClaimsIntakeState(
        last_asked_field="injuries_reported",
        last_asked_group=["injuries_reported", "third_parties_involved"],
    )

    updated = extract_fields("no", state)

    assert updated.injuries_reported is False
    assert updated.third_parties_involved is False


def test_single_yes_no_field_fallback_still_works_outside_the_combo_group() -> None:
    """The combo-check reordering must not regress the plain single-field case (e.g.
    vehicle_drivable, asked on its own, not as part of the injuries+third-parties group)."""
    state = ClaimsIntakeState(
        last_asked_field="vehicle_drivable", last_asked_group=["vehicle_drivable"]
    )

    updated = extract_fields("no", state)

    assert updated.vehicle_drivable is False


def test_opening_message_with_several_facts_extracts_location_without_being_asked() -> None:
    """PBI-09-01 final validation: an opening message packing several facts into one sentence
    ("...chocamos ayer en Avenida Reforma, Ciudad de Mexico...") never had its explicit "en
    <place>" location extracted at all — only a *follow-up* answer to a location-specific
    question ever triggered it. A caller who volunteers the location up front must not be asked
    for it again. Also regresses a second, related defect found in the same live test: the
    trailing ", no hubo lesionados" clause (comma-joined, no period) must not be swept into the
    location — a real address never contains ", no "."""
    state = extract_fields(
        "Choqué ayer en Avenida Reforma, Ciudad de Mexico, no hubo lesionados.",
        ClaimsIntakeState(),
    )

    assert state.event_location == "Avenida Reforma, Ciudad de Mexico"


def test_en_realidad_filler_phrase_is_never_mistaken_for_a_location() -> None:
    """PBI-09-01 final validation: making location extraction unconditional (previous test)
    initially reintroduced a worse defect — "En realidad, volvamos a mi accidente." (a domain
    switch-back message, "Actually, let's go back to my claim.") was silently captured as
    event_location = "realidad, volvamos a mi accidente", since "en" is also the start of the
    common Spanish discourse filler "en realidad" ("actually"). This corruption was invisible
    to the user (the visible question still looked correct) but would have permanently blocked
    the real location from ever being asked for."""
    state = extract_fields("En realidad, volvamos a mi accidente.", ClaimsIntakeState())

    assert state.event_location is None


def test_free_text_fallback_fills_the_last_asked_free_text_field() -> None:
    state = ClaimsIntakeState(last_asked_field="event_location")

    updated = extract_fields("in the parking lot of my office", state)

    assert updated.event_location == "in the parking lot of my office"


def test_free_text_fallback_does_not_apply_to_structured_fields() -> None:
    """A malformed date answer must not silently land in event_date — it should stay missing
    so the workflow re-prompts, per PBI-01-05's 'invalid date/time format' edge case."""
    state = ClaimsIntakeState(last_asked_field="event_date")

    updated = extract_fields("last Tuesday sometime", state)

    assert updated.event_date is None


def test_free_text_fallback_is_skipped_when_a_structured_field_matched_instead() -> None:
    state = ClaimsIntakeState(last_asked_field="customer_name")

    updated = extract_fields("it's SYN-POL-0002", state)

    assert updated.customer_name is None
    assert updated.policy_number == "SYN-POL-0002"


def test_free_text_fallback_never_overwrites_an_already_filled_field() -> None:
    state = ClaimsIntakeState(last_asked_field="event_location", event_location="already set")

    updated = extract_fields("something else entirely", state)

    assert updated.event_location == "already set"


def test_grouped_question_recovers_event_location_alongside_a_structured_date() -> None:
    """Regression guard: a combined "what date, where, and what type of loss?" question sets
    last_asked_field to only the first field in the group (event_date) — event_location must
    still be captured from the same reply via last_asked_group, not silently dropped just
    because a structured field (the date) also matched in the same message."""
    state = ClaimsIntakeState(
        last_asked_field="event_date",
        last_asked_group=["event_date", "event_location", "loss_type"],
    )

    updated = extract_fields("2026-08-07, en Avenida Reforma, Ciudad de Mexico", state)

    assert updated.event_date == "2026-08-07"
    assert updated.event_location == "Avenida Reforma, Ciudad de Mexico"


def test_grouped_question_does_not_recover_event_location_when_not_part_of_the_group() -> None:
    state = ClaimsIntakeState(
        last_asked_field="contact_phone", last_asked_group=["contact_phone"]
    )

    updated = extract_fields("2026-08-07", state)

    assert updated.event_location is None


def test_resolve_selection_matches_a_spanish_ordinal_word() -> None:
    candidates = [
        PolicyCandidate(
            policy_number="SYN-POL-1001", customer_name="Juan Pérez", line_of_business="auto",
            vehicle_description="Nissan Sentra 2022",
        ),
        PolicyCandidate(
            policy_number="SYN-POL-1002", customer_name="Juan Pérez", line_of_business="auto",
            vehicle_description="Toyota Hilux 2021",
        ),
    ]

    assert resolve_selection("la segunda", candidates).policy_number == "SYN-POL-1002"


def test_resolve_selection_matches_a_vehicle_description_word_in_a_short_reply() -> None:
    """Regression guard: the caller's reply ("la Hilux") is much shorter than the full stored
    description ("Toyota Hilux 2021") — matching must look for the description's own words
    inside the reply, not the other way around."""
    candidates = [
        PolicyCandidate(
            policy_number="SYN-POL-1001", customer_name="Juan Pérez", line_of_business="auto",
            vehicle_description="Nissan Sentra 2022",
        ),
        PolicyCandidate(
            policy_number="SYN-POL-1002", customer_name="Juan Pérez", line_of_business="auto",
            vehicle_description="Toyota Hilux 2021",
        ),
    ]

    assert resolve_selection("la Hilux", candidates).policy_number == "SYN-POL-1002"


def test_resolve_selection_returns_none_for_an_unrecognizable_reply() -> None:
    candidates = [
        PolicyCandidate(
            policy_number="SYN-POL-1001", customer_name="Juan Pérez", line_of_business="auto",
            vehicle_description="Nissan Sentra 2022",
        ),
    ]

    assert resolve_selection("no estoy seguro", candidates) is None


def test_resolve_selection_tolerates_trailing_punctuation_on_the_selected_word() -> None:
    """Regression guard: "La Hilux." (capitalized, trailing period) must still resolve —
    found via live DEV validation when a punctuation-attached word broke the exact word-set
    match against the stored vehicle_description."""
    candidates = [
        PolicyCandidate(
            policy_number="SYN-POL-1001", customer_name="Juan Pérez", line_of_business="auto",
            vehicle_description="Nissan Sentra 2022",
        ),
        PolicyCandidate(
            policy_number="SYN-POL-1002", customer_name="Juan Pérez", line_of_business="auto",
            vehicle_description="Toyota Hilux 2021",
        ),
    ]

    assert resolve_selection("La Hilux.", candidates).policy_number == "SYN-POL-1002"


def test_resolve_selection_ordinal_tolerates_trailing_punctuation() -> None:
    candidates = [
        PolicyCandidate(
            policy_number="SYN-POL-1001", customer_name="Juan Pérez", line_of_business="auto",
            vehicle_description="Nissan Sentra 2022",
        ),
        PolicyCandidate(
            policy_number="SYN-POL-1002", customer_name="Juan Pérez", line_of_business="auto",
            vehicle_description="Toyota Hilux 2021",
        ),
    ]

    assert resolve_selection("la segunda,", candidates).policy_number == "SYN-POL-1002"


def test_grouped_question_extracts_a_clean_location_from_a_rich_multi_clause_message() -> None:
    """Regression guard found via live DEV validation: a rich message combining a relative
    date, a loss-type keyword embedded in a conjugated verb ("chocaron"), a location, and
    separate injuries/third-parties/vehicle-drivable clauses must not let the location capture
    spill into the following sentence."""
    state = ClaimsIntakeState(
        last_asked_field="event_date",
        last_asked_group=["event_date", "event_location", "loss_type"],
    )

    updated = extract_fields(
        "Ayer me chocaron por atrás en Reforma. Yo manejaba, no hubo lesionados ni "
        "terceros y el vehículo todavía puede circular.",
        state,
    )

    assert updated.event_location == "Reforma"
    assert updated.loss_type == "collision"
    assert updated.injuries_reported is False
    assert updated.third_parties_involved is False
    assert updated.vehicle_drivable is True


def test_direct_answer_to_event_location_is_not_dropped_by_an_unrelated_fact_in_the_same_message() -> (
    None
):
    """Regression guard found via live DEV validation: when directly asked "¿Dónde ocurrió el
    incidente?" (last_asked_field == "event_location", a single-field ask, not the grouped
    fallback path), a reply that also happens to mention an unrelated fact (injuries) in the
    same message must still have its own direct answer captured — not silently dropped just
    because injuries_reported was also extracted from that message."""
    state = ClaimsIntakeState(last_asked_field="event_location")

    updated = extract_fields(
        "En mi casa en Colonia Roma. Se dañaron los muebles de la sala, no hubo lesionados y "
        "todavía podemos permanecer en la casa.",
        state,
    )

    assert updated.event_location is not None
    assert updated.injuries_reported is False
    assert updated.property_habitable is True


def test_direct_location_ask_extracts_a_clean_place_from_a_rich_multi_clause_reply() -> None:
    """Regression guard found via live DEV validation: a direct "¿Dónde ocurrió el incidente?"
    ask (last_asked_field == "event_location" exactly, not the grouped-question path) that
    receives a rich, multi-clause reply must still extract a clean place name, not the entire
    raw message verbatim."""
    state = ClaimsIntakeState(last_asked_field="event_location")

    updated = extract_fields(
        "En mi casa en Colonia Roma. Se dañaron los muebles de la sala, no hubo lesionados y "
        "todavía podemos permanecer en la casa.",
        state,
    )

    assert updated.event_location == "mi casa en Colonia Roma"
    assert "Se dañaron los muebles" not in updated.event_location
    assert "lesionados" not in updated.event_location


def test_direct_location_ask_falls_back_to_the_whole_message_with_no_connector_word() -> None:
    state = ClaimsIntakeState(last_asked_field="event_location")

    updated = extract_fields("In my driveway", state)

    assert updated.event_location == "In my driveway"

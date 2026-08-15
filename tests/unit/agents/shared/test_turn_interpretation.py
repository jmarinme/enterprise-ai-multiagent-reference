"""Unit tests for TurnInterpretation and to_domain_interpretation (PBI-14-04): the shared,
pre-routing structured shape and its adapter into each domain's legacy
Claims/Broker/CommercialSemanticInterpretation shape, so no workflow.py signature had to change
to reuse it.
"""

from typing import Any

from src.agents.shared.semantic_models import (
    AlternativeIntent,
    BrokerEntities,
    BrokerSemanticInterpretation,
    ClaimsEntities,
    ClaimsSemanticInterpretation,
    CommercialEntities,
    CommercialSemanticInterpretation,
    SemanticInterpretation,
    TurnInterpretation,
    _empty_domain_interpretation,
    to_domain_interpretation,
)


def test_to_domain_interpretation_picks_only_the_matching_entities() -> None:
    # A well-behaved model (per the shared prompt's own instructions) only ever populates the
    # ONE entities object matching its primary `intent` — the other two stay null.
    turn = TurnInterpretation(
        intent="claims",
        intent_confidence=0.9,
        claims_entities=ClaimsEntities(loss_type="collision"),
        broker_entities=None,
        commercial_entities=None,
    )

    claims_interpretation = to_domain_interpretation(turn, ClaimsSemanticInterpretation)
    broker_interpretation = to_domain_interpretation(turn, BrokerSemanticInterpretation)
    commercial_interpretation = to_domain_interpretation(turn, CommercialSemanticInterpretation)

    assert claims_interpretation.entities.loss_type == "collision"
    # Requesting a domain the model did not populate degrades to empty entities, never an error
    # and never fabricated data — e.g. a low-confidence-fallback turn routed to a different
    # agent than the one the LLM originally classified.
    assert broker_interpretation.entities.broker_name is None
    assert commercial_interpretation.entities.company_name is None


def test_to_domain_interpretation_preserves_confidence_and_confirmation() -> None:
    turn = TurnInterpretation(intent="claims", intent_confidence=0.77, confirmation=True)

    interpretation = to_domain_interpretation(turn, ClaimsSemanticInterpretation)

    assert interpretation.intent_confidence == 0.77
    assert interpretation.confirmation is True


def test_to_domain_interpretation_flattens_alternative_intents_to_plain_strings() -> None:
    turn = TurnInterpretation(
        intent="broker_services",
        intent_confidence=0.5,
        alternative_intents=[AlternativeIntent(intent="commercial_intake", confidence=0.45)],
    )

    interpretation = to_domain_interpretation(turn, BrokerSemanticInterpretation)

    assert interpretation.alternative_intents == ["commercial_intake"]


def test_to_domain_interpretation_degrades_safely_when_turn_is_none() -> None:
    """Mirrors src.agents.shared.semantic_interpreter._empty's own fallback shape — used when a
    specialist Agent is called directly with no Supervisor in front of it."""
    interpretation = to_domain_interpretation(None, ClaimsSemanticInterpretation)

    assert interpretation.intent == "unknown"
    assert interpretation.intent_confidence == 0.0
    assert interpretation.entities == ClaimsEntities()


def test_turn_interpretation_schema_never_exposes_chain_of_thought() -> None:
    """CLAUDE.md §10 / PBI-14-04 section 4: routing_reason is a short safe label, never a
    reasoning field — assert no such field exists on the shared shape at all."""
    schema = TurnInterpretation.model_json_schema()

    forbidden_terms = ("reasoning", "chain_of_thought", "thought", "rationale", "thinking")
    property_names = {name.lower() for name in schema.get("properties", {})}
    assert not (property_names & set(forbidden_terms))


# ---------------------------------------------------------------------------------------------
# PBI-14-10: Azure/OpenAI Structured Outputs strict-mode schema-compliance regression tests.
#
# Root cause this guards against: a live DEV Azure OpenAI HTTP 400 on every real semantic-
# routing call, because Pydantic's default model_json_schema() output does not satisfy
# strict=True's contract (every object must set additionalProperties=false; every defined
# property must appear in `required`, with optionality expressed via nullable type unions, never
# by omission). Fixed via a shared `_strict_schema_extra` model_config hook (see
# src.agents.shared.semantic_models) applied to every class actually sent to Azure OpenAI as
# response_schema (src.llm.models.LLMResponseSchema, strict=True by default, unchanged by this
# PBI) — never by touching field types/defaults/validation, routing logic, confidence
# thresholds, prompts, or RuleBasedIntentResolver keywords.
#
# This test walks the REAL, actual model_json_schema() output (never a hand-written expected
# schema) so it fails automatically the moment ANY future field is added to one of these classes
# without the class carrying the compliance hook — the exact regression class this PBI fixes.
# ---------------------------------------------------------------------------------------------


def _assert_object_schema_is_strict_compatible(path: str, defn: dict[str, Any]) -> None:
    if "properties" not in defn:
        return  # not an object schema (e.g. a bare array/$ref wrapper) - nothing to check here
    properties = set(defn["properties"].keys())
    required = set(defn.get("required", []))
    assert defn.get("additionalProperties") is False, (
        f"{path}: additionalProperties must be exactly False for Azure/OpenAI Structured "
        f"Outputs strict=True (got {defn.get('additionalProperties')!r})"
    )
    assert required == properties, (
        f"{path}: every defined property must appear in `required` under strict=True — "
        f"missing {properties - required!r} (unexpected extra: {required - properties!r})"
    )


def _assert_full_schema_is_strict_compatible(model: type) -> None:
    schema = model.model_json_schema()
    _assert_object_schema_is_strict_compatible(f"{model.__name__} (root)", schema)
    for def_name, def_schema in schema.get("$defs", {}).items():
        _assert_object_schema_is_strict_compatible(
            f"{model.__name__} -> $defs.{def_name}", def_schema
        )


def test_turn_interpretation_family_schemas_are_azure_openai_strict_compatible() -> None:
    """PBI-14-10: TurnInterpretation and every nested object it can generate (AlternativeIntent,
    ClaimsEntities, BrokerEntities, CommercialEntities) must satisfy strict=True — this is the
    exact schema sent for the Supervisor's one pre-routing semantic call."""
    _assert_full_schema_is_strict_compatible(TurnInterpretation)


def test_alternative_intent_schema_is_azure_openai_strict_compatible() -> None:
    _assert_full_schema_is_strict_compatible(AlternativeIntent)


def test_entity_schemas_are_azure_openai_strict_compatible() -> None:
    _assert_full_schema_is_strict_compatible(ClaimsEntities)
    _assert_full_schema_is_strict_compatible(BrokerEntities)
    _assert_full_schema_is_strict_compatible(CommercialEntities)


def test_semantic_interpretation_family_schemas_are_azure_openai_strict_compatible() -> None:
    """PBI-14-10: SemanticInterpretation and its three domain subclasses (each specialist
    Agent's own backward-compat direct-call fallback path, src.agents.shared.semantic_interpreter
    §4 call sites) share the identical defect class TurnInterpretation had — verified here so a
    currently-latent path never surfaces the same live HTTP 400 the moment it IS exercised."""
    _assert_full_schema_is_strict_compatible(SemanticInterpretation)
    _assert_full_schema_is_strict_compatible(ClaimsSemanticInterpretation)
    _assert_full_schema_is_strict_compatible(BrokerSemanticInterpretation)
    _assert_full_schema_is_strict_compatible(CommercialSemanticInterpretation)


def test_semantically_optional_fields_remain_nullable_after_strict_fix() -> None:
    """The strict-mode fix moves every field into `required`, but genuinely optional fields
    (as opposed to always-populated collections like `corrections`) must still be representable
    as null — required-but-nullable, never required-and-non-null, which would make it
    impossible for the model to say 'no value' for e.g. routing_reason/claims_entities."""
    schema = TurnInterpretation.model_json_schema()
    for field_name in (
        "routing_reason",
        "confirmation",
        "claims_entities",
        "broker_entities",
        "commercial_entities",
    ):
        field_schema = schema["properties"][field_name]
        types_present = {option.get("type") for option in field_schema.get("anyOf", [])}
        assert "null" in types_present, f"{field_name} must remain nullable after the strict fix"


def test_confidence_bounds_unchanged_by_strict_fix() -> None:
    """PBI-14-10 must not touch confidence semantics — only schema required/additionalProperties
    metadata changed."""
    turn_schema = TurnInterpretation.model_json_schema()
    assert turn_schema["properties"]["intent_confidence"]["minimum"] == 0.0
    assert turn_schema["properties"]["intent_confidence"]["maximum"] == 1.0

    alt_schema = AlternativeIntent.model_json_schema()
    assert alt_schema["properties"]["confidence"]["minimum"] == 0.0
    assert alt_schema["properties"]["confidence"]["maximum"] == 1.0


def test_empty_turn_interpretation_construction_unchanged_by_strict_fix() -> None:
    """The exact minimal-kwargs shape src.agents.shared.semantic_interpreter._empty() uses for
    TurnInterpretation must keep working — the strict-mode fix only changes the JSON SCHEMA sent
    to Azure OpenAI, never Python-level field defaults or constructor requirements."""
    empty = TurnInterpretation(intent="unknown", intent_confidence=0.0)

    assert empty.intent == "unknown"
    assert empty.intent_confidence == 0.0
    assert empty.claims_entities is None
    assert empty.broker_entities is None
    assert empty.commercial_entities is None
    assert empty.alternative_intents == []


def test_empty_domain_interpretation_construction_unchanged_by_strict_fix() -> None:
    """Mirrors _empty_domain_interpretation()'s own exact minimal-kwargs call shape."""
    empty = _empty_domain_interpretation(ClaimsSemanticInterpretation)

    assert empty.intent == "unknown"
    assert empty.intent_confidence == 0.0
    assert empty.entities == ClaimsEntities()


def test_partial_json_parsing_unchanged_by_strict_fix() -> None:
    """The strict-mode `required` array governs what Azure OpenAI must EMIT, not how already-
    received JSON is parsed back into these classes — existing mock-provider test fixtures (and
    any real LLM response that happens to omit default-valued fields) must keep parsing
    identically to before this PBI."""
    partial_json = (
        '{"intent": "claims", "intent_confidence": 0.94, '
        '"routing_reason": "User is reporting damage.", '
        '"claims_entities": {"event_date": "2026-08-14", "loss_type": "collision"}}'
    )

    parsed = TurnInterpretation.model_validate_json(partial_json)

    assert parsed.intent == "claims"
    assert parsed.intent_confidence == 0.94
    assert parsed.requires_clarification is False  # omitted field, still defaults correctly
    assert parsed.broker_entities is None  # omitted field, still defaults correctly
    assert parsed.claims_entities is not None
    assert parsed.claims_entities.event_date == "2026-08-14"
    assert parsed.claims_entities.customer_name is None  # omitted nested field, still defaults

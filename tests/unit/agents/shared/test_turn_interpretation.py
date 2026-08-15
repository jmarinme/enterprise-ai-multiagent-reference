"""Unit tests for TurnInterpretation and to_domain_interpretation (PBI-14-04): the shared,
pre-routing structured shape and its adapter into each domain's legacy
Claims/Broker/CommercialSemanticInterpretation shape, so no workflow.py signature had to change
to reuse it.
"""

import pytest
from pydantic import ValidationError

from src.agents.shared.semantic_models import (
    AlternativeIntent,
    BrokerEntities,
    BrokerSemanticInterpretation,
    ClaimsEntities,
    ClaimsSemanticInterpretation,
    CommercialEntities,
    CommercialSemanticInterpretation,
    CorrectionEntry,
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
# PBI-14-10 + PBI-14-12B: Azure/OpenAI Structured Outputs strict-mode schema-compliance
# regression tests.
#
# Root cause this guards against: a live DEV Azure OpenAI HTTP 400 on every real semantic-
# routing call. PBI-14-10 fixed one defect class (additionalProperties/required at the object
# level). PBI-14-12's live diagnosis proved that fix was INCOMPLETE — the checker below (before
# PBI-14-12B) only inspected object schemas that already had a `properties` key
# (`if "properties" not in defn: return`), so it silently skipped `corrections`' free-form-map
# schema entirely, and it never checked for unsupported keywords at all (Field(ge=..., le=...)
# rendering `minimum`/`maximum` into the schema). PBI-14-12B fixes both the production schemas
# AND this checker.
#
# The checker below is deliberately NOT a mirror of src.agents.shared.semantic_models'
# _strict_schema_extra implementation (checking "did the hook run" would trivially pass even if
# the hook itself were wrong, exactly as happened before PBI-14-12B). Instead it is built
# independently from Azure OpenAI's own documented JSON Schema support/limitations
# (learn.microsoft.com/en-us/azure/foundry/openai/how-to/structured-outputs, "JSON Schema
# support and limitations" — fetched live during PBI-14-12's diagnosis, 2026-08-15) and recurses
# into every place a nested schema can appear: root, $defs, properties, anyOf branches, and array
# items — so it fails on a genuine violation regardless of which mechanism (or lack of one)
# produced the schema.
# ---------------------------------------------------------------------------------------------

# Azure OpenAI Structured Outputs' own documented "Unsupported type-specific keywords" table,
# transcribed independently of anything in src.agents.shared.semantic_models.
_AZURE_UNSUPPORTED_KEYWORDS_BY_TYPE: dict[str, set[str]] = {
    "string": {"minLength", "maxLength", "pattern", "format"},
    "number": {"minimum", "maximum", "multipleOf"},
    "integer": {"minimum", "maximum", "multipleOf"},
    "object": {
        "patternProperties",
        "unevaluatedProperties",
        "propertyNames",
        "minProperties",
        "maxProperties",
    },
    "array": {
        "unevaluatedItems",
        "contains",
        "minContains",
        "maxContains",
        "minItems",
        "maxItems",
        "uniqueItems",
    },
}


def _walk_schema_for_violations(node: object, path: str, violations: list[str]) -> None:
    """Recurses into every place Azure OpenAI would itself need to validate: this node, its
    object properties, array items, and anyOf branches — independent of $ref/$defs resolution
    order, so a violation nested arbitrarily deep is still found."""
    if not isinstance(node, dict):
        return

    node_type = node.get("type")

    if node_type in _AZURE_UNSUPPORTED_KEYWORDS_BY_TYPE:
        present = _AZURE_UNSUPPORTED_KEYWORDS_BY_TYPE[node_type] & node.keys()
        for keyword in sorted(present):
            violations.append(
                f"{path}: unsupported keyword {keyword!r} present on type={node_type!r} "
                f"(Azure OpenAI Structured Outputs strict mode does not support this)"
            )

    if node_type == "object":
        additional_properties = node.get("additionalProperties", "<absent>")
        if additional_properties is not False:
            violations.append(
                f"{path}: additionalProperties must be exactly False, got "
                f"{additional_properties!r} — a schema value here (not the literal False) means "
                f"an arbitrary-key dictionary/map, which strict mode cannot express"
            )
        if "properties" not in node:
            violations.append(
                f"{path}: type=object with no 'properties' key at all — this is a free-form "
                f"map/dictionary schema (e.g. Pydantic's rendering of dict[str, X]), "
                f"structurally incompatible with strict mode regardless of additionalProperties"
            )
        else:
            properties = set(node["properties"].keys())
            required = set(node.get("required", []))
            if required != properties:
                violations.append(
                    f"{path}: every defined property must appear in required under strict=True "
                    f"— missing {properties - required!r} (unexpected extra: "
                    f"{required - properties!r})"
                )

    for prop_name, prop_schema in node.get("properties", {}).items():
        _walk_schema_for_violations(prop_schema, f"{path}.{prop_name}", violations)
    if "items" in node:
        _walk_schema_for_violations(node["items"], f"{path}[]", violations)
    for index, branch in enumerate(node.get("anyOf", [])):
        _walk_schema_for_violations(branch, f"{path}(anyOf[{index}])", violations)


def _assert_full_schema_is_strict_compatible(model: type) -> None:
    schema = model.model_json_schema()
    violations: list[str] = []
    _walk_schema_for_violations(schema, f"{model.__name__} (root)", violations)
    for def_name, def_schema in schema.get("$defs", {}).items():
        _walk_schema_for_violations(
            def_schema, f"{model.__name__} -> $defs.{def_name}", violations
        )
    assert not violations, f"{model.__name__}: " + "; ".join(violations)


def test_turn_interpretation_family_schemas_are_azure_openai_strict_compatible() -> None:
    """PBI-14-10 + PBI-14-12B: TurnInterpretation and every nested object it can generate
    (AlternativeIntent, ClaimsEntities, BrokerEntities, CommercialEntities, CorrectionEntry) must
    satisfy strict=True — this is the exact schema sent for the Supervisor's one pre-routing
    semantic call, and the one PBI-14-12 proved was actually failing live in DEV."""
    _assert_full_schema_is_strict_compatible(TurnInterpretation)


def test_alternative_intent_schema_is_azure_openai_strict_compatible() -> None:
    _assert_full_schema_is_strict_compatible(AlternativeIntent)


def test_entity_schemas_are_azure_openai_strict_compatible() -> None:
    _assert_full_schema_is_strict_compatible(ClaimsEntities)
    _assert_full_schema_is_strict_compatible(BrokerEntities)
    _assert_full_schema_is_strict_compatible(CommercialEntities)


def test_correction_entry_schema_is_azure_openai_strict_compatible() -> None:
    """PBI-14-12B: the fixed-shape replacement for the old free-form corrections dict."""
    _assert_full_schema_is_strict_compatible(CorrectionEntry)


def test_semantic_interpretation_family_schemas_are_azure_openai_strict_compatible() -> None:
    """PBI-14-10 + PBI-14-12B: SemanticInterpretation and its three domain subclasses (each
    specialist Agent's own backward-compat direct-call fallback path,
    src.agents.shared.semantic_interpreter §4 call sites) share the identical defect classes
    TurnInterpretation had — verified here so a currently-latent path never surfaces the same
    live HTTP 400 the moment it IS exercised."""
    _assert_full_schema_is_strict_compatible(SemanticInterpretation)
    _assert_full_schema_is_strict_compatible(ClaimsSemanticInterpretation)
    _assert_full_schema_is_strict_compatible(BrokerSemanticInterpretation)
    _assert_full_schema_is_strict_compatible(CommercialSemanticInterpretation)


def test_checker_actually_detects_a_free_form_map_violation() -> None:
    """Proves the checker is a real oracle, not a rubber stamp: a deliberately reintroduced
    free-form dict[str, str] property must be caught."""
    from pydantic import BaseModel, ConfigDict

    from src.agents.shared.semantic_models import _strict_schema_extra

    class _Regression(BaseModel):
        model_config = ConfigDict(json_schema_extra=_strict_schema_extra)
        bad_field: dict[str, str] = {}

    violations: list[str] = []
    _walk_schema_for_violations(_Regression.model_json_schema(), "_Regression (root)", violations)
    assert any("free-form map" in v for v in violations)


def test_checker_actually_detects_an_unsupported_numeric_keyword_violation() -> None:
    """Proves the checker catches minimum/maximum even if a future field reintroduces
    Field(ge=..., le=...) on a class whose hook is bypassed or missing."""
    violations: list[str] = []
    _walk_schema_for_violations(
        {"type": "object", "properties": {"x": {"type": "number", "minimum": 0.0}}},
        "synthetic",
        violations,
    )
    assert any("minimum" in v for v in violations)


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


def test_confidence_schema_no_longer_declares_minimum_maximum() -> None:
    """PBI-14-12B: minimum/maximum are on Azure OpenAI's own documented unsupported-keyword list
    for Number types — confirmed via PBI-14-12's live diagnosis to be part of why every real
    semantic-routing call was failing with a 400. The OUTBOUND schema must no longer declare
    them; see test_confidence_bounds_enforced_at_runtime_after_numeric_keyword_strip immediately
    below for proof this does not weaken Pydantic's own runtime validation."""
    turn_schema = TurnInterpretation.model_json_schema()
    assert "minimum" not in turn_schema["properties"]["intent_confidence"]
    assert "maximum" not in turn_schema["properties"]["intent_confidence"]

    alt_schema = AlternativeIntent.model_json_schema()
    assert "minimum" not in alt_schema["properties"]["confidence"]
    assert "maximum" not in alt_schema["properties"]["confidence"]


def test_confidence_bounds_enforced_at_runtime_after_numeric_keyword_strip() -> None:
    """PBI-14-12B must NOT weaken application-level validation merely to satisfy Azure's schema
    — stripping minimum/maximum from the OUTBOUND schema is a request-construction concern only;
    Field(ge=0.0, le=1.0) still rejects out-of-range values at Python construction time and at
    model_validate_json parse time, completely independent of what the schema dict declares."""
    with pytest.raises(ValidationError):
        TurnInterpretation(intent="claims", intent_confidence=1.5)
    with pytest.raises(ValidationError):
        TurnInterpretation(intent="claims", intent_confidence=-0.1)
    with pytest.raises(ValidationError):
        AlternativeIntent(intent="claims", confidence=1.5)
    with pytest.raises(ValidationError):
        TurnInterpretation.model_validate_json(
            '{"intent": "claims", "intent_confidence": 2.0}'
        )

    # In-range values still construct and parse normally.
    ok = TurnInterpretation(intent="claims", intent_confidence=0.85)
    assert ok.intent_confidence == 0.85


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


def test_corrections_round_trips_as_correction_entry_list() -> None:
    """PBI-14-12B: corrections changed from dict[str, str] to list[CorrectionEntry] to satisfy
    Azure OpenAI Structured Outputs strict mode (a free-form dict cannot set
    additionalProperties=false). Same semantic content — which field, and its corrected value —
    must survive construction, JSON serialization, and re-parsing unchanged."""
    turn = TurnInterpretation(
        intent="claims",
        intent_confidence=0.9,
        corrections=[
            CorrectionEntry(field="event_date", corrected_value="2026-08-14"),
            CorrectionEntry(field="loss_type", corrected_value="collision"),
        ],
    )

    dumped = turn.model_dump_json()
    parsed = TurnInterpretation.model_validate_json(dumped)

    assert parsed.corrections == [
        CorrectionEntry(field="event_date", corrected_value="2026-08-14"),
        CorrectionEntry(field="loss_type", corrected_value="collision"),
    ]

    # to_domain_interpretation forwards corrections unchanged (type-agnostic passthrough).
    domain = to_domain_interpretation(turn, ClaimsSemanticInterpretation)
    assert domain.corrections == turn.corrections


def test_empty_corrections_list_behaves_like_the_old_empty_dict() -> None:
    """src.supervisor.semantic_routing._is_empty_sentinel checks `not turn.corrections` —
    an empty list must be just as falsy as the old empty dict was, so that check's behavior is
    unchanged by this PBI."""
    turn = TurnInterpretation(intent="unknown", intent_confidence=0.0)
    assert turn.corrections == []
    assert not turn.corrections


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

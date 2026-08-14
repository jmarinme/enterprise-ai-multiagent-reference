"""Shared semantic-entity merge (PBI-14-03 section 7).

Applies a domain's SemanticInterpretation.entities onto that domain's already
deterministically-extracted state, filling ONLY fields the deterministic extractor left empty.
This is what "reuse the existing call, do not replace deterministic extraction" (sections 4/6)
means in code: each Agent's own extraction.extract_fields always runs first and always wins on
a conflict; semantic entities only ever fill a genuine gap.

Merge precedence (section 7), as implemented end-to-end across this module, each
extraction.py, and src.agents.shared.memory: Tool-verified fact (never touched here) >
explicit deterministic extraction from the current message (extraction.py, already applied
before this runs) > high-confidence semantic extraction from the current message (this module,
gated by MIN_CONFIDENCE_TO_APPLY) > previously confirmed conversation memory
(src.agents.shared.memory, applied before extraction.py ever runs) > low-confidence inferred
information (never auto-applied).
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

StateT = TypeVar("StateT", bound=BaseModel)

# Below this confidence, semantic entities are never applied (CLAUDE.md §3 / PBI-14-03 section
# 7: "low-confidence info must not silently become business truth"). A caller whose own
# intent this interpretation call was unsure about should not also have its extracted entities
# trusted as if they were deterministic facts.
MIN_CONFIDENCE_TO_APPLY = 0.5


def apply_semantic_entities(  # noqa: UP047
    state: StateT,
    entities: BaseModel,
    intent_confidence: float,
    *,
    fields: tuple[str, ...],
) -> tuple[StateT, list[str]]:
    """Return (updated_state, applied_field_names).

    Only ever sets a field on `state` that is currently None and for which `entities` supplies
    a non-None value, and only when intent_confidence meets MIN_CONFIDENCE_TO_APPLY — never
    overwrites an already-populated field (deterministic extraction, Tool-verified data, or
    memory prefill all already ran and take precedence)."""
    if intent_confidence < MIN_CONFIDENCE_TO_APPLY:
        return state, []
    updates: dict[str, object] = {}
    applied: list[str] = []
    for field in fields:
        if getattr(state, field, None) is not None:
            continue
        value = getattr(entities, field, None)
        if value is not None:
            updates[field] = value
            applied.append(field)
    if not updates:
        return state, []
    return state.model_copy(update=updates), applied

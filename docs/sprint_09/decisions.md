# Sprint 09 Decisions

## D-01: Global memory is Agent-owned via a shared metadata key, not Supervisor-owned

See `implementation-plan.md`'s design-decision section. Chosen for zero blast radius on
`SupervisorOrchestrator`/`ConversationContext`/`AgentResponse` and consistency with the existing
explicit-metadata-threading convention (`language`, per-agent state).

## D-02: Memory pre-fill applies only on an Agent's first turn in the conversation

Gating on `state.status == <Status>.NEW` prevents a stale memory value from silently overwriting
a caller's in-progress correction (e.g. Claims' confirmation-decline flow, which deliberately
clears incident fields to `None` so the next turn can re-collect them). See
`implementation-plan.md` for the full reasoning.

## D-03: `customer_name` is reused across Claims/Commercial Intake without distinguishing "the
policyholder" from "the commercial contact person"

`ConversationMemory.customer_name` is a single field per the PBI's own specified 15-field shape
(no separate "contact_name" vs "policyholder_name" distinction was requested). In a real
production system a commercial lead's contact person is not necessarily the same individual as a
personal-lines policyholder; for this synthetic, single-caller academic reference platform, the
simplification (last agent to resolve a name wins) matches the PBI's literal memory-field list
and its explicit "do not add new business features" constraint (which forecloses adding a second,
undistinguished field the PBI never asked for). Documented here as a known, intentional trade-off
rather than an oversight.

## D-04: `reference_numbers` is append-only, computed at each call site rather than inside
`update_memory`

`update_memory`'s generic overlay (`model_copy(update=...)`) is correct for every scalar field —
a newer non-empty value should simply replace an older one. A list field needs different
semantics (accumulate, never replace), so each Agent computes the merged list itself
(`memory.reference_numbers + [new_ref]`, de-duplicated) before calling `update_memory`, rather
than adding special-cased list-merging logic to the shared helper for a single field — keeping
`update_memory` itself simple and predictable for every other field (CLAUDE.md §7: smallest
viable change, no premature generalization).

## D-05: The existing grouped-question UX in Claims is preserved, not un-grouped

Requirement 5 ("ask ONLY the highest priority missing field... never ask multiple questions if
one answer can unlock others") was interpreted as: never ask for an *identifier* that
entity-resolution/memory could have supplied — not as a mandate to replace Claims' already-shipped,
already-tested "ask 2-3 genuinely-independent incident-detail fields in one natural message"
grouping (PBI-04-04's own explicit "natural conversation" requirement). Un-grouping it would be an
unrequested UX regression and a architecture-adjacent change beyond this PBI's explicit "do not
redesign architecture" instruction. Memory pre-fill (D-01/D-02) is what actually eliminates
redundant questions across domains; the requirement is satisfied by that, not by dismantling an
unrelated, working design.

## D-07: Final validation defects were fixed surgically, not by broadening the memory-prefill gate uniformly

Investigating defect #1 (domain re-entry misattribution) revealed the original PBI-09-01 design
choice — gate memory pre-fill to an Agent's first turn only — was too conservative for Broker and
Commercial (which have no field-clearing/decline transition, so re-applying memory every turn is
provably safe) while remaining necessary for Claims (whose confirmation-decline flow deliberately
clears incident-detail fields). Rather than adopt one uniform rule, each Agent's gate was tuned to
its own actual risk profile — see `implementation-plan.md`'s original D-02 for the base rule and
`broker_agent.py`/`commercial_intake_agent.py`'s own updated docstrings for the per-Agent
reasoning. This is the same "smallest viable, provably-correct change" bias the rest of this
codebase's extraction modules already follow.

## D-06: `src/supervisor/intent.py`'s Spanish "póliza" keyword gap was found but left unfixed

While designing acceptance tests, a pre-existing gap was found: `_BROKER_KEYWORDS` includes
English "policy" but not Spanish "póliza"/"poliza", so a bare Spanish policy-status opener with no
other Broker keyword would resolve to `UNKNOWN`/`FallbackAgent` on a brand-new conversation. This
predates PBI-09-01, is not one of its 11 numbered requirements, and this PBI's explicit
instructions forbid touching Supervisor routing/architecture. Flagged here for a future PBI
rather than fixed silently in scope-creep.

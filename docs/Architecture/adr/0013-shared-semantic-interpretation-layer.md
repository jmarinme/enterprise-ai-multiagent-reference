# ADR-0013: Shared Semantic Interpretation Layer for Multi-Agent Conversational Intelligence

## Status

Accepted and implemented — 2026 (PBI-14-01 gap analysis, PBI-14-03 implementation). Live for
all three specialist agents: Claims, Broker Services, and Commercial Intake.

## Context

PBI-14-01's gap analysis found the platform's conversational behavior was closer to a rigid,
field-by-field form than an LLM-assisted conversation: a rich, multi-fact Claims message
correctly extracted structured facts (date/location/loss type) via regex but still re-asked for
a description already implicit in that same message; "sip" was not understood as an
affirmative; Commercial Intake's compound requests ("quiero asegurar una fábrica... contra
incendio") risked misrouting to Claims on the bare keyword "incendio"; and a lead was registered
automatically the instant the last required field was filled, with no explicit confirmation
step. The root, reusable cause: every specialist agent already made one real LLM call per turn
(`src.agents.shared.annotation.annotate_with_prompt_and_llm`), but its actual completion text
was discarded in favor of a fixed `[prompt=...] [llm=...]` diagnostic string — the call was
"wired but wasted."

## Decision

Repurpose the existing per-turn LLM call into one shared, typed semantic-interpretation
abstraction, rather than adding new LLM round-trips or building three independent
conversational engines:

- **`src.llm.models.LLMResponseSchema`** + `LLMRequest.response_schema` (additive fields) let a
  caller request structured JSON output; `AzureOpenAIProvider` maps this to
  `response_format={"type": "json_schema", ...}`, and `MockLLMProvider` gained
  `structured_response_plan`/`structured_response_sequence` to script deterministic structured
  completions in tests.
- **`src.agents.shared.semantic_models`** defines one shared shape (`SemanticInterpretation`:
  intent, intent_confidence, alternative_intents, confirmation, corrections, already_answered,
  missing_information) plus three domain `entities` submodels
  (`ClaimsEntities`/`BrokerEntities`/`CommercialEntities`) mapped onto each Agent's own real
  `*IntakeState`/`*InquiryState` fields — never invented fields, and never a chain-of-thought
  field (CLAUDE.md §10).
- **`src.agents.shared.semantic_interpreter.interpret_semantics`** replaces
  `annotate_with_prompt_and_llm` at each Agent's one call site: same prompt identifier, same one
  LLM call per turn, now returning a real parsed interpretation instead of a discarded
  completion. Degrades to a safe, empty, zero-confidence interpretation on any Prompt/LLM/parse
  failure — the deterministic business flow is never blocked.
- **`src.agents.shared.semantic_merge.apply_semantic_entities`** fills a state field from the
  interpretation's entities ONLY when the field is still `None` after each Agent's existing
  deterministic `extraction.extract_fields()` runs, and only above a minimum confidence
  (`MIN_CONFIDENCE_TO_APPLY = 0.5`). Deterministic extraction always runs first and always wins
  a conflict — this is strictly additive to the existing, already-tested extraction logic.
- **`src.agents.shared.confirmation.resolve_confirmation`** replaces Claims'/Broker's duplicated
  (and Commercial's absent) yes/no word lists with one shared, expanded deterministic word set
  ("sip", "va", "nel", "todavía no", ...), falling back to the interpretation's own
  `.confirmation` field only when the deterministic fast path is inconclusive.
- **`src.supervisor.intent.RuleBasedIntentResolver`** gained a narrow, still fully deterministic
  compound-pattern rule (`_is_new_commercial_insurance_request`: an "asegurar"-family verb AND a
  business-premises noun) checked before the Claims keyword list, resolving the
  incendio/fábrica collision without any LLM involvement in routing — plus two confirmed keyword
  gaps (accented "póliza", bare "pago").
- **`CommercialIntakeState`/`workflow.py`** gained a `CONFIRMING` status (mirroring Claims'
  existing pattern) between `COLLECTING_INFORMATION` and `READY_TO_REGISTER`, plus
  `industry`/`location`/`insured_value` qualification-only fields — a lead is no longer
  registered automatically the instant the last required field is filled.

## Why the Supervisor was NOT made LLM-informed

Section 5 of the driving PBI suggested semantic intent could "inform" routing. The only
reusable LLM call happens inside a specialist agent, *after* the Supervisor has already
deterministically picked that agent — using it to *re-route* would require either a new
pre-routing LLM call (violating the "zero new LLM calls" requirement) or restructuring
`SupervisorOrchestrator` into an LLM-informed router (a materially larger, riskier change than
this PBI's scope, and a stricter reading of ADR-0011's "Supervisor remains deterministic"
boundary than the letter of the request required). Instead, the Supervisor gained a stronger,
still 100%-deterministic keyword-disambiguation rule that fixes the one concrete regression case
required, and the semantic interpretation is used only *within* whichever agent the Supervisor
already selected — never for same-turn re-routing. This keeps ADR-0011's boundary intact rather
than weakening it.

## Why entity extraction is a MERGE, not a replacement

Every existing `extraction.py` module's regex/keyword logic was already tested and working for
the cases it covers (PBI-01-05 through PBI-09-01). Rewriting it to depend on the LLM would both
regress well-tested deterministic behavior and violate CLAUDE.md §3 ("the LLM is not the source
of truth") more directly than a fallback-only merge does. `apply_semantic_entities`'s
confidence gate and "only fill an empty field" rule are the two safeguards that keep this
change strictly additive: nothing a real deployment already did correctly can change, and a
low-confidence interpretation can never silently become business fact.

## Architecture (before/after)

```
Before: User Message -> Deterministic Supervisor -> Specialist Agent
                                                        |-> extract_fields() [deterministic]
                                                        |-> advance_*_intake() [state machine]
                                                        `-> annotate_with_prompt_and_llm()
                                                            [LLM call; text discarded]

After:  User Message -> Deterministic Supervisor (+ narrow compound-keyword rule)
                          -> Specialist Agent
                               |-> interpret_semantics() [the SAME one LLM call, now structured]
                               |-> advance_*_intake(semantic=...)
                               |     |-> extract_fields() [deterministic, unchanged, first]
                               |     |-> apply_semantic_entities() [fills gaps only, confidence-gated]
                               |     `-> resolve_confirmation() [shared word set + semantic fallback]
                               `-> ToolCallingOrchestrator (ReAct) [unchanged, isolated, additive]
```

ReAct/Tool Calling (ADR-0011) is untouched: `ToolCallingOrchestrator` still runs as the same
isolated, additive capability alongside each Agent's deterministic state machine, never fed by
or feeding into the semantic interpretation layer.

## Alternatives considered

- **Three independent per-agent conversational engines.** Rejected: the PBI explicitly required
  one shared abstraction; three copies would triple the surface for the same bug class PBI-14-01
  found (e.g. Commercial's missing confirmation logic existing nowhere to copy from).
- **A new, separate LLM call per turn for semantic interpretation.** Rejected: would double LLM
  calls/cost/latency per turn for no correctness benefit — the existing annotation call was
  already budgeted and already fired every turn; repurposing it is strictly better.
- **Route based on semantic intent instead of deterministic keywords.** Rejected — see "Why the
  Supervisor was NOT made LLM-informed" above.
- **Let low-confidence semantic entities become business truth immediately.** Rejected:
  `MIN_CONFIDENCE_TO_APPLY` exists specifically to prevent a plausible-sounding but wrong
  extraction from silently overwriting a field the deterministic layer legitimately left
  unknown.

## Consequences

- Positive: multi-field extraction, natural confirmation understanding, and explicit
  pre-registration confirmation now work uniformly across all three agents, closing the specific
  regressions PBI-14-01 found, with zero net increase in LLM calls per turn.
- Positive: `intent_confidence`/`routing_reason`/`routing_source` are now real, non-fabricated
  observability signals (`src.supervisor.orchestrator._routing_diagnostics`,
  `AgentResponse.routing_diagnostics` — deliberately not the persisted `metadata` channel, so
  routing telemetry never bloats the Conversation document). The `$0.0000` cost bug
  (`ConversationSummary.total_estimated_cost_usd` coercing an unknown price to 0.0) is fixed at
  both the in-memory and Cosmos aggregation layers plus the API response model.
- Negative / accepted: `interpret_semantics` now depends on the deployed model actually
  supporting `response_format=json_schema`; a model/deployment that does not degrades to the
  same safe empty-interpretation fallback as any other LLM failure — never a crash, but also no
  semantic enrichment for that turn.
- Negative / accepted: Commercial Intake's conversation now takes one more turn than before this
  PBI (an explicit confirmation) — an intentional Human-in-the-Loop safety improvement
  (CLAUDE.md §5), not a defect.
- Follow-up (not built): per-field provenance telemetry (which fields came from extraction vs.
  memory vs. Tools vs. semantic inference) and confirmation-retry/repeated-question counters
  (PBI-14-03 sections 20-21) were intentionally left unbuilt — the driving PBI scoped
  observability as secondary and explicitly warned against another observability redesign; these
  remain honestly `None`/absent rather than fabricated.

## Relationship with other ADRs

- [ADR-0011](0011-react-pattern-for-tool-orchestrated-reasoning.md) — this ADR's semantic
  interpretation layer sits strictly upstream of, and is never fed by, the ReAct/Tool-Calling
  loop that ADR-0011 governs; both remain isolated, additive capabilities alongside the
  deterministic state machines.
- [ADR-0006](0006-provider-abstraction-pattern.md) — `LLMResponseSchema`/structured output is an
  additive capability on the existing `LLMProvider` abstraction, not a new provider type.
- [ADR-0012](0012-observability-persistence-model.md) — this ADR's routing/cost telemetry fixes
  populate real values into the schema ADR-0012 already defined (`RunRecord.intent_confidence`/
  `routing_reason`, `ConversationSummary.total_estimated_cost_usd`); no schema redesign.

## Review triggers

- Before adding a second semantic-interpretation LLM call per turn for any reason — revisit
  whether the existing one call can be extended first (per this ADR's own "zero new LLM calls"
  constraint).
- Before letting semantic interpretation influence same-turn Supervisor routing — see "Why the
  Supervisor was NOT made LLM-informed"; that would be a materially different decision requiring
  its own ADR.
- Before building per-field provenance or confirmation-retry telemetry (Follow-up above) — scope
  it explicitly rather than growing it incrementally into another observability redesign.
- If a deployed model's `response_format=json_schema` support changes (e.g. a new reasoning-
  family capability gap, mirroring PBI-03-05/03-06's temperature findings) — revisit
  `interpret_semantics`'s degrade-on-failure behavior.

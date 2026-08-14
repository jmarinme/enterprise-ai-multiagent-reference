# ADR-0014: Semantic-First Supervisor Routing

## Status

Accepted and implemented — 2026 (PBI-14-04). Live for all three specialist agents and
FallbackAgent.

## Context

PBI-14-03 (ADR-0013) made semantic interpretation real inside each specialist agent, but live
Azure validation surfaced the deeper architectural gap that work never touched: the Supervisor
still routed on `RuleBasedIntentResolver`'s deterministic keyword matching alone, and the one
per-turn semantic call only ran *after* an agent was already selected. A message with no exact
domain keyword — the reported live failure was "quiero reportar un percance derivado de la
fuerte lluvia que cayó hoy un camión me pegó por atrás" — never matched any
`_CLAIMS_KEYWORDS`/`_BROKER_KEYWORDS`/`_COMMERCIAL_KEYWORDS` entry, so
`RuleBasedIntentResolver` returned `UNKNOWN`, and the Supervisor routed straight to
`FallbackAgent` — which never calls an LLM at all — before ClaimsAgent's own, already-correct
semantic layer ever got the chance to understand the message.

## Decision

Move the ONE per-turn semantic call from inside each specialist agent to the Supervisor, to run
*before* routing, and have the selected specialist reuse its result — never a second call for
the same turn:

- **`src.agents.shared.semantic_models.TurnInterpretation`** (+ `AlternativeIntent`) is the new
  shared, pre-routing structured shape: `intent` (one of four wire-level strings: `claims`,
  `broker_services`, `commercial_intake`, `unknown`), `intent_confidence`,
  `alternative_intents`, `requires_clarification`, `confirmation`, `corrections`,
  `already_answered`, `missing_information`, a short safe `routing_reason` label (never chain-
  of-thought), and three OPTIONAL per-domain entity objects (`claims_entities`/
  `broker_entities`/`commercial_entities`) populated in the SAME call — no second request is
  needed merely because the domain schema differs once routing is known.
- **`configs/prompts/supervisor/turn_interpretation.md`** is the new shared prompt this call
  renders — framed around "what is the caller's CURRENT GOAL," explicitly walking through the
  incendio/fábrica collision case so the model classifies by intent, not by isolated keyword.
- **`src.supervisor.semantic_routing.resolve_turn`** calls
  `src.agents.shared.semantic_interpreter.interpret_semantics` (unchanged, reused verbatim —
  the exact same function PBI-14-03 already used) once, then applies fixed, deterministic
  Python conditionals — confidence thresholds (`SemanticRoutingConfig.high_confidence`/
  `low_confidence`, exposed via `SupervisorConfig`), a keyword-corroboration check at medium
  confidence, and a `RuleBasedIntentResolver` fallback when the semantic call itself degrades —
  to produce a `RoutingDecision`. The Supervisor never "reasons": every branch is a plain `if`.
- **`SupervisorOrchestrator`** gained two new constructor dependencies
  (`PromptManager`/`LLMProvider` — reusing the exact same cached instances every agent already
  used) and now calls `resolve_turn` before `_resolve_agent`, then passes the resulting
  `TurnInterpretation` (+ its diagnostic string) into `agent.handle(...,
  turn_interpretation=..., turn_interpretation_diagnostic=...)`.
- **The `Agent` Protocol** (`src.supervisor.registry`) gained these two new, optional
  (default `None`/`""`) parameters. Each specialist agent's `handle()` now reuses a non-None
  `turn_interpretation` via `src.agents.shared.semantic_models.to_domain_interpretation` (an
  adapter back into the unchanged `Claims/Broker/CommercialSemanticInterpretation` shapes each
  `workflow.py` already expected — zero workflow signature changes) instead of calling
  `interpret_semantics` itself. When `turn_interpretation` is `None` (no Supervisor in front —
  e.g. a direct unit test), the agent degrades to calling `interpret_semantics` itself, exactly
  matching PBI-14-03's own behavior — a backward-compatible resilience path, not a normal-path
  second call.
- **`FallbackAgent`** gained the same two parameters and now distinguishes a genuine "no idea"
  message from a `requires_clarification` case, asking one of three fixed, deterministic,
  bilingual clarification questions (never LLM-authored prose) naming the two plausible
  domains — e.g. "¿Quieres revisar una póliza o comisión existente, o cotizar protección para un
  nuevo negocio?" for the Broker/Commercial pair.

## Why the Supervisor still never "reasons"

`resolve_turn` consumes the LLM's structured output as DATA — every routing outcome is produced
by a fixed set of Python conditionals (confidence ≥ threshold, keyword corroboration agrees,
etc.), the same shape of logic `RuleBasedIntentResolver` already used on keyword matches. This
is not a qualitatively different Supervisor architecture, only a richer, pre-computed input to
the same kind of deterministic decision tree — ADR-0011's "Supervisor remains deterministic"
boundary is preserved, not weakened.

## Why entities travel in the SAME call, not a second one

The PBI's central constraint is zero net new semantic LLM calls per turn. Splitting "classify
intent" and "extract domain entities" into two calls (one pre-routing, one post-routing) would
have doubled the call count for exactly the turns this PBI most wants to fix (a rich, keyword-
free message). Nesting three optional, domain-typed entity objects in `TurnInterpretation`
(rather than a discriminated union) keeps the schema a single flat structured-output request —
compatible with the same Azure OpenAI `response_format=json_schema` mechanism PBI-14-03 already
wired up (`src.llm.models.LLMResponseSchema`), with typed Pydantic validation on every field.

## Why `RuleBasedIntentResolver` was kept, not deleted

Per the driving PBI, `RuleBasedIntentResolver` is now explicitly a resilience/fallback
mechanism, not the primary router: (a) when `interpret_semantics` itself degrades (Prompt/LLM
failure, or a malformed structured response — both detected via
`src.supervisor.semantic_routing._semantic_call_succeeded`, which checks both the diagnostic
string AND whether the returned interpretation exactly matches the safe-empty sentinel shape,
since a parse failure still carries a "[llm=...]" diagnostic), and (b) as a cheap corroboration
signal for a medium-confidence semantic result. No new keyword synonyms were added to it for
this PBI — the two confirmed PBI-14-03 keyword gaps (`póliza`, `pago`) and the compound
incendio/fábrica rule already exist from that ADR and were left untouched.

## Architecture (before/after)

```
BEFORE (PBI-14-03):
User Message -> Deterministic Supervisor (RuleBasedIntentResolver, keyword-only)
                  -> Specialist Agent (or FallbackAgent, which never calls an LLM)
                       `-> ONE semantic interpretation call [too late to affect routing]
                       `-> ReAct / Tool Calling [unchanged]

AFTER (PBI-14-04):
User Message -> ONE semantic turn interpretation (src.supervisor.semantic_routing.resolve_turn)
                  -> Deterministic Supervisor routing rules (confidence thresholds,
                     keyword-corroboration, RuleBasedIntentResolver as fallback only)
                  -> Specialist Agent (or FallbackAgent, now clarification-aware)
                       `-> REUSES the same interpretation — never re-requested
                       `-> ReAct / Tool Calling [unchanged, still isolated and additive]
```

## Alternatives considered

- **Make the Supervisor itself an LLM-driven ReAct agent.** Rejected outright per the driving
  PBI's own non-negotiable principle — routing must stay deterministic and reproducible
  (ADR-0011).
- **Two semantic calls per turn (one for routing, one for entities, inside the selected
  agent).** Rejected: doubles cost/latency for exactly the turns this PBI most wants fixed, and
  the driving PBI explicitly required "if this would need two calls, stop and explain the
  blocker" — nesting all three domains' entities in one schema avoided that blocker entirely.
- **A discriminated union (`entities: ClaimsEntities | BrokerEntities | CommercialEntities`)
  keyed by intent, instead of three optional named fields.** Rejected: Azure OpenAI structured
  output (`response_format=json_schema`) has materially better-understood support for a flat
  object with nullable named fields than for a Python-style tagged union translated into JSON
  Schema `oneOf`; three optional fields is also simpler to validate and adapt back into the
  existing per-domain shapes with zero ambiguity.
- **Delete `RuleBasedIntentResolver` entirely now that semantic routing exists.** Rejected —
  see "Why RuleBasedIntentResolver was kept" above; PBI-14-04 section 17 explicitly requires a
  deterministic fallback for when the semantic call is unavailable.
- **Let the LLM's `alternative_intents` text double as the clarification question shown to the
  user.** Rejected: CLAUDE.md's architecture principle #2 keeps user-facing business response
  text deterministic; `FallbackAgent`'s fixed, reviewable template catalog (keyed by the pair of
  plausible domains) is used instead — the LLM only ever supplies which two domains are
  plausible, never the wording.

## Consequences

- Positive: the specific reported live defect (a keyword-free Claims message reaching
  FallbackAgent) is fixed, along with the general class of paraphrase/compound/current-goal
  messages PBI-14-01/14-03 already showed the specialist agents' own semantic layer could
  understand, if only routing gave it the chance.
- Positive: zero net increase in normal-turn semantic LLM calls — verified by a call-counting
  test (`tests/unit/supervisor/test_pbi_14_04_production_regression.py`) asserting exactly one
  structured call per turn end to end through Supervisor + ClaimsAgent + real Tools.
- Positive: genuine cross-domain ambiguity ("quiero revisar lo de mi negocio") now produces a
  deterministic clarifying question instead of either a wrong guess or a generic "I don't
  understand."
- Negative / accepted: `SupervisorOrchestrator` now depends on `PromptManager`/`LLMProvider` —
  a real, intentional widening of its dependency surface (previously only
  `ConversationRepository`/`IntentResolver`/`AgentRegistry`). This is the necessary cost of
  moving semantic understanding earlier in the pipeline; it does not weaken the "Supervisor
  never imports a concrete Agent implementation" boundary, which is unchanged.
- Negative / accepted: confidence thresholds (`0.7`/`0.4` defaults) are operational starting
  values, not calibrated against real production traffic — flagged explicitly in
  `SemanticRoutingConfig`'s own docstring and here, not silently presented as tuned.
- Follow-up (not built): per-turn A/B comparison or calibration tooling for the confidence
  thresholds: out of scope for this PBI, which only had to make routing correct, not optimal.

## Relationship with other ADRs

- [ADR-0013](0013-shared-semantic-interpretation-layer.md) — this ADR relocates WHEN the one
  shared semantic call PBI-14-03/ADR-0013 introduced runs (before routing instead of after),
  and extends its shape (`SemanticInterpretation` -> `TurnInterpretation`); it does not replace
  ADR-0013's merge-precedence, confirmation, or per-agent extraction design, all of which are
  unchanged and still described accurately there.
- [ADR-0011](0011-react-pattern-for-tool-orchestrated-reasoning.md) — ReAct/Tool-Calling is
  untouched by this ADR; see "Why the Supervisor still never reasons" above for how this ADR's
  own routing logic stays consistent with ADR-0011's deterministic-Supervisor boundary.
- [ADR-0012](0012-observability-persistence-model.md) — this ADR populates three new, additive
  `RunRecord` fields (`routing_source`, `requires_clarification`, `alternative_intents`) into
  the schema ADR-0012 already defined; no persistence-model redesign.

## Review triggers

- Before adding a second semantic LLM call anywhere in the normal per-turn path — revisit
  whether `TurnInterpretation` can be extended first, per this ADR's own "zero new calls"
  constraint.
- Before recalibrating `SemanticRoutingConfig`'s thresholds from real production data — record
  the measured precision/recall this ADR's defaults lacked.
- Before letting the Supervisor's routing decision depend on anything other than
  `TurnInterpretation` + `RuleBasedIntentResolver` (e.g. a second model call, a different
  scoring mechanism) — that would be a materially different decision requiring its own ADR.
- If `RuleBasedIntentResolver`'s fallback role is ever removed or replaced — update this ADR's
  "kept, not deleted" section.

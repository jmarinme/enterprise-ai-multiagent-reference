# ADR-0011: Adoption of ReAct Pattern for Tool-Orchestrated Reasoning

## Status

Accepted and implemented — 2026 (PBI-12-01 gap analysis, PBI-12-04 generalization). Live in
DEV for all three specialist agents: Claims, Broker Services, and Commercial Intake.

## Context

The course's Agentic AI requirement names ReAct (Reason + Act) + Tool Calling as the primary
pattern to demonstrate. A dedicated gap analysis (PBI-12-01) inspected the current
implementation against that requirement in detail and found a more nuanced state than "ReAct is
missing": `ToolCallingOrchestrator.run()` (`src/core/tool_calling/orchestrator.py`) already
implemented a bounded Reason → Act → Observe → Reason loop — calling the LLM, executing any
requested Tool, feeding the result back as an Observation for a further LLM call, bounded by
`max_iterations` — and this was already covered by 15 dedicated tests, including multi-iteration
sequences and a max-iterations-exceeded case. What was actually missing was narrower: this loop
was wired into exactly one Agent (`ClaimsAgent`, PBI-02-04), used as an isolated, additive
capability that never drove the deterministic business flow; `BrokerAgent` and
`CommercialIntakeAgent` still made at most one LLM call per turn with no Tool-result feedback
loop; and nothing in the codebase — no prompt, no docstring, no ADR — named this mechanism as
ReAct or explained why it was built this way.

## Decision

Generalize the existing `ToolCallingOrchestrator` to all three specialist agents (PBI-12-04),
rather than building a second reasoning engine:

- **`BrokerAgent`** and **`CommercialIntakeAgent`** each gained a `ToolCallingOrchestrator`
  field and a `_run_controlled_tool_calling` method, structurally identical to `ClaimsAgent`'s
  existing one — additive, isolated, never feeding into `BrokerInquiryState`/
  `CommercialIntakeState`. All three agents share the exact same cached, process-wide
  `ToolCallingOrchestrator` instance (`apps/api/src/api/dependencies.py`'s
  `get_tool_calling_orchestrator()`) — never a second, competing orchestration engine.
- **`ClaimsAgent`'s own behavior was not changed** beyond prompt wording — its existing,
  already-tested wiring is exactly what the other two agents were generalized to match.
- **Prompts** for all three agents (`configs/prompts/claims/system.md`,
  `broker_services/system.md`, `commercial_intake/system.md`) now explicitly instruct the model
  to reason using a Reason → determine whether a Tool is required → Action → Observation →
  Reason → ... → Final Answer process, and explicitly never to reveal that internal reasoning —
  only the Final Answer reaches the user.
- **Hardening added to the shared orchestrator** (`src/core/tool_calling/orchestrator.py`),
  applying uniformly to all three agents: duplicate-tool-call detection (a call with the same
  tool name and arguments as one already made earlier in the same loop is rejected with a typed
  `duplicate_call` error, never re-executed) and an optional per-LLM-call `timeout_seconds`
  (`ToolCallingContext.timeout_seconds`, default `None` — opt-in, preserves every existing
  caller's exact prior behavior). `max_iterations` (pre-existing, default 3) is unchanged and
  reused, not reimplemented.

### Why ReAct was selected as the primary pattern

It was not newly selected — it was already the architecture's answer to "how does an Agent use a
Tool," from PBI-02-04 onward, before this ADR existed to name it. This ADR formalizes and
generalizes a decision the codebase had already made in practice: an LLM that can only reason
once per turn, with no way to observe a Tool's result before finishing its answer, cannot verify
or correct itself against real data. A bounded Reason/Act/Observe loop is what lets the model's
final answer be grounded in an actual Tool outcome, not just its own single-pass guess.

### Why the Supervisor remains deterministic

`SupervisorOrchestrator` (`src/supervisor/orchestrator.py`) calls `RuleBasedIntentResolver`
(`src/supervisor/intent.py`) — keyword matching, explicitly documented as "No LLM, no
embeddings, no AI of any kind" — and never imports or references any concrete Agent
implementation. This boundary was not touched by PBI-12-04 and must not be: routing which
specialist agent handles a message is a governance decision (per-agent permitted scope, CLAUDE.md
§2), and a governance decision must stay reproducible and auditable, not subject to a model's
own reasoning. ReAct's iterative, LLM-driven loop is the right tool for "how does an agent
answer a question it doesn't yet have enough information for" — it is the wrong tool for "which
of four agents is authorized to handle this message," which has a single correct, testable
answer every time.

### Why reasoning happens inside specialist agents

Each specialist agent — not the Supervisor, not a new shared top-level layer — is where the
domain-specific Tool allow-list and domain-specific prompt already live
(`src.core.tool_calling.policies.CLAIMS_ALLOWED_TOOLS`/`BROKER_ALLOWED_TOOLS`/
`COMMERCIAL_ALLOWED_TOOLS`). A shared execution layer already existed for this
(`ToolCallingOrchestrator` itself, under `src/core/`, agent-agnostic) — what was missing was
adoption, not a new layer. Putting the ReAct loop inside each agent keeps the authorization
boundary (which Tools this agent may ever call) co-located with the reasoning that requests
them, and keeps the Supervisor's own boundary (described above) completely unchanged.

### Why Tool Calling remains deterministic

The Reason/Observe steps are the LLM's; the Act step never is. `ToolCallingOrchestrator.
_execute_tool_call` validates a requested tool's existence and authorization against
`ToolRegistry`/`ToolCallingContext.allowed_tools` before ever invoking `Tool.execute()` — no
eval, no dynamic import, no shell execution, and (new in PBI-12-04) no re-execution of an
already-attempted identical call. The LLM can request an action; only deterministic code decides
whether that action actually runs. This is unchanged by generalizing the loop to three agents —
if anything, it now applies uniformly instead of only to one.

## Architecture pattern inventory (post-PBI-12-04)

| Category | Pattern | Status |
|---|---|---|
| **Primary** | ReAct + Tool Calling | Implemented — bounded Reason/Act/Observe loop, all three specialist agents |
| Complementary | Multi-Agent | Implemented — Supervisor + Claims/Broker/Commercial Intake |
| Complementary | Planner–Executor | Implemented — Supervisor plans (routes), each Agent executes |
| Complementary | Memory | Implemented — Cosmos DB conversational memory, cross-agent slot filling |
| Complementary | Guardrails | Implemented — Entra ID + JWT/JWKS validation + deterministic Tool authorization |
| Future | LLM-as-a-Judge | Not implemented — no self-evaluation of a response's quality/correctness exists today |
| Future | Self-Reflection | Not implemented — no mechanism revisits or critiques a prior reasoning step |

## Alternatives considered

- **Build a new, separate ReAct engine rather than generalizing `ToolCallingOrchestrator`.**
  Rejected: the existing engine already satisfied every mechanical requirement (bounded loop,
  observation feedback, typed results, 15 passing tests) — a second engine would duplicate
  tested logic for no benefit and directly violate the explicit instruction not to build a new
  orchestration engine.
- **Wire ReAct into the deterministic workflow/state-machine layer
  (`advance_claims_intake`/`advance_broker_inquiry`/`advance_commercial_intake`) instead of
  keeping it isolated.** Rejected: those state machines are this platform's actual business-fact
  source of truth (CLAUDE.md §3) — dict-dispatched, deterministic, already fully tested. Routing
  LLM reasoning through them would make business outcomes depend on model behavior, exactly what
  CLAUDE.md's "LLM is not the source of truth" principle forbids. The isolated/additive pattern
  ClaimsAgent already established was kept unchanged for this reason, not merely out of caution.
- **Move ReAct into the Supervisor so routing itself could reason about ambiguous messages.**
  Rejected: see "Why the Supervisor remains deterministic" above — this would make routing
  non-reproducible and harder to audit, for a problem (routing) that keyword matching already
  solves deterministically.
- **Persist the model's intermediate reasoning (Thought/Observation text) for debugging.**
  Rejected: CLAUDE.md §10 explicitly forbids storing hidden chain-of-thought. `ToolCallingResponse
  .text` (the loop's own final text) is structurally discarded by every Agent's
  `_run_controlled_tool_calling` caller — only the typed `tool_calls` list (no free-text
  reasoning field on `ToolCallResult`) and the deterministic business response are ever
  persisted or shown to the user, verified by dedicated tests
  (`test_isolated_tool_calling_reasoning_text_never_leaks_into_the_visible_response`,
  `test_isolated_tool_calling_reasoning_text_is_never_persisted_in_metadata`, added to both new
  Broker/Commercial test files).
- **Give each agent its own separate `ToolCallingOrchestrator` instance instead of sharing one.**
  Rejected: no per-agent state exists on the orchestrator (duplicate-call tracking is local to
  a single `run()` invocation, never stored on `self`) — sharing one process-wide instance is
  strictly more consistent with this codebase's existing composition-root pattern (one cached
  `ToolRegistry`, one cached `ToolExecutor`, one cached `LLMProvider`) and avoids a pointless
  second object with identical behavior.

## Consequences

- Positive: the course's named primary pattern (ReAct + Tool Calling) is now demonstrable
  end-to-end on all three specialist agents, not just one, with dedicated tests proving it for
  each.
- Positive: duplicate-tool-call detection and an optional per-call timeout are now available to
  every agent using this orchestrator, closing two of the gaps PBI-12-01's analysis identified,
  with zero behavior change for any caller that does not opt into the timeout.
- Positive: zero regression — all 682 previously-passing backend tests plus 18 new ones (700
  total) pass; `ruff`/`mypy` clean on every touched file; frontend `vitest`/`build` unaffected
  (this PBI touched no frontend code).
- Negative / accepted: Broker and Commercial Intake now make up to `max_iterations` additional
  LLM calls per turn in their isolated ReAct path (previously zero, beyond the one existing
  annotation call) — a real latency/cost increase for those two agents, bounded by the same
  `max_iterations` cap Claims already accepted.
- Negative / accepted: a pre-existing gap discovered while generalizing this pattern — Claims'
  isolated tool-calling path only catches `ToolCallingError`, not a genuine `LLMProvider`
  failure, which would propagate uncaught through `SupervisorOrchestrator` and crash the whole
  turn. This was **not** fixed in Claims (explicitly out of scope — preserve Claims' existing
  behavior unless the change is documentation or prompt wording); Broker's and Commercial
  Intake's new isolated paths were built with a broader `except Exception` from day one, so they
  do not carry this same fragility. Tracked as remaining technical debt — see the final report.
- Follow-up (not built): LLM-as-a-Judge and Self-Reflection remain named as future evolution
  only, per the course's own pattern taxonomy — no code path implements either today.

## Relationship with other ADRs

- [ADR-0006](0006-provider-abstraction-pattern.md) — `ToolCallingOrchestrator` is consumed as a
  shared, injectable dependency exactly like every other provider abstraction in this codebase.
- [ADR-0007](0007-ai-governance-boundary.md) — this ADR's "Tool Calling remains deterministic"
  section is a direct extension of ADR-0007's own governance boundary to the now-generalized
  ReAct loop.
- [ADR-0010](0010-enterprise-authentication-entra-id.md) — unrelated layer, unaffected: identity
  validation happens before any agent (and therefore before any ReAct loop) is ever reached.

## Review triggers

- Before implementing LLM-as-a-Judge or Self-Reflection — revisit whether either belongs inside
  the existing isolated path or requires its own governance boundary discussion.
- Before allowing the isolated ReAct path's output to influence a deterministic business
  decision (it does not today, by design) — that would be a materially different decision
  requiring its own ADR, not an incremental change to this one.
- If Claims' known error-handling gap (see Consequences) is ever fixed — update this ADR to
  note the asymmetry is resolved.
- Before raising `max_iterations` materially above its current default (3) for any agent —
  reconsider the latency/cost tradeoff explicitly, not silently.

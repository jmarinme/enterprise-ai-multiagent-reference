# Sprint 09 — Conversation Intelligence & Multi-domain Orchestration

## Objective

Make the existing multi-agent platform behave like one intelligent insurance assistant instead
of three independent forms. No new business capability, no architecture redesign, no Azure/
Bicep/CI-CD change — only reasoning, orchestration, memory, and conversation-quality
improvements layered on top of the existing Supervisor/Agent/Tool architecture.

## Scope

- [x] PBI-09-01: Global conversation memory shared across Claims/Broker/Commercial Intake,
      slot filling before asking, natural-language date/weather extraction extensions,
      conversation-progress summarization, Mexico-appropriate broker wording, and acceptance
      tests for cross-domain intent switching.
- [x] PBI-09-01 Final Conversational Validation: live, realistic multi-turn conversation testing
      (14 scenarios through the real FastAPI app, not unit tests alone) across Claims/Broker/
      Commercial and every domain-switch direction; 7 real conversational defects found and
      fixed (one of them a regression introduced by an earlier fix in this same pass, caught by
      re-running the full scenario suite after every change), each with a regression test.

## Out of scope

- Any change to `ops/bicep/`, `azure-pipelines*`, or deployed Azure resources.
- Any new Tool, business rule, or capability (CLAUDE.md §2 permitted-scope boundaries for each
  Agent are unchanged).
- Any change to the Supervisor's intent-resolution keyword lists (`src/supervisor/intent.py`) —
  a known, pre-existing gap (Spanish "póliza" not in `_BROKER_KEYWORDS`) was identified but left
  untouched; it predates this PBI and is not part of its explicit requirements.
- Re-architecting the grouped-question design in `src/agents/claims/state.py` — the "ask only
  the highest-priority missing field" requirement is satisfied by never asking for a field
  memory already resolved, not by un-grouping the existing, already-validated "ask 2-3 related
  incident-detail fields together" UX.

## Deliverables

- [x] PBI-09-01: Conversation Intelligence & Multi-domain Orchestration.
- [x] PBI-09-01 Final Conversational Validation.

## Acceptance criteria

See `docs/sprint_09/validation.md` for the full mapping of PBI-09-01's 11 numbered requirements
to the code that satisfies each one and the tests that prove it.

## Dependencies

Builds directly on PBI-05-01's cross-agent state carry-forward mechanism
(`src/agents/shared/state_persistence.py`) and PBI-04-04's bilingual message/language
infrastructure (`src/agents/shared/language.py`, `messages.py`) — no new infrastructure
dependency introduced.

## Risks

- `Conversation.metadata` is strictly `dict[str, str]`, replaced (never merged) every turn — the
  new `globalMemory` key follows the same explicit-echo-forward pattern every other per-agent
  state key already uses, so this is a known, already-mitigated risk, not a new one.
- Cross-domain reuse of `customer_name` (e.g., a Commercial Intake contact name overwriting a
  Claims customer name) is a deliberate simplification for this synthetic, single-caller academic
  scope — see `decisions.md`.

## Deliverable Log

- PBI-09-01: Global conversation memory, slot filling, entity-resolution reuse, natural-language
  extraction extensions, conversation summarization, Mexico-appropriate broker wording, and 21
  new acceptance/unit tests — 2026-08-10.
- PBI-09-01 Final Conversational Validation: 14 live scenarios run through the real FastAPI app;
  7 defects found and fixed (domain re-entry misattribution, accent-insensitive name lookup,
  Broker combined-question `last_asked_field` gap, English relative dates unsupported, injuries+
  third-parties combo-"no" dead code, opening-message location extraction/trailing-clause
  pollution, and a filler-phrase ["en realidad"] false positive introduced by the location-
  extraction fix itself and caught by re-running the full scenario suite); 17 new regression
  tests — 2026-08-10.

## Sprint validation

See `docs/sprint_09/validation.md`.

## Sprint retrospective

Every requirement was deliverable as an additive layer on the existing deterministic
state-machine agents — no case required inventing a new Tool, a new metadata mechanism, or a
departure from the "LLM is not the source of truth" principle. The one real design decision
(where global memory is owned) was resolved in favor of each Agent explicitly loading/updating
it, matching the codebase's existing explicit-metadata-threading convention (language, per-agent
state) rather than introducing a new implicit Supervisor-level side channel.

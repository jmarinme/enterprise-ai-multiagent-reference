# Sprint 05 — Intelligent Conversational Experience

## Objective

Make Claims, Broker, and Commercial feel like an intelligent insurance assistant instead of a
deterministic questionnaire: natural Spanish entity extraction, multi-fact-per-turn capture,
contextual Supervisor handoffs, line-of-business-aware Claims profiles (Auto/Property), natural
customer/broker discovery, and a richer, internally-consistent synthetic demo portfolio —
without introducing new Agents, new infrastructure, or making business facts LLM-authored.

## Scope

- [x] PBI-05-01: Intelligent Conversational Experience + Line-of-Business-Aware Claims +
      Synthetic Demo Data Expansion.

## Out of scope

- New Agents (no AutoClaimsAgent/PropertyClaimsAgent — one ClaimsAgent, profile-driven).
- New Azure resources, RBAC, networking, QA/Prod environments.
- Real LLM-authored business facts or response text (architecture principle #2 unchanged).
- Entra ID (still deferred, per Sprint 04).

## Acceptance criteria

See `decisions.md` and `validation.md` for the full, evidence-backed accounting against this
PBI's own STOP CONDITION list.

## Dependencies

- Sprint 04's Spanish-first foundation (`src/agents/shared/{language,messages}.py`), customer
  discovery, coverage validation, confirmation gate, and conversation-history endpoints — this
  PBI extends all of them, replacing none.

## Risks

See `decisions.md`.

## Deliverable Log

<!-- Append entries. Do not remove previous entries. -->

PBI-05-01: Shared Conversational Policy + NLU helpers, LOB-aware Claims (Auto/Property) via one
`ClaimsAgent`, natural customer/broker discovery, contextual Supervisor handoff (incl. a
pre-existing `current_agent` persistence bug fix), expanded synthetic demo portfolio, referential
consistency tests, 5 live-DEV bugs found/fixed, `ca-tmxap-dev-api` redeployed (`ca-tmxap-dev-web`
unchanged, no frontend changes required) — 2026-08-08. Evidence: `validation.md`, `decisions.md`.

## Sprint validation

See `validation.md`. Final regression (2026-08-08): backend 551 passed/2 skipped, ruff clean,
mypy clean; frontend 33 tests passed, typecheck clean, lint clean. All 4 live DEV scenarios
(A–D) completed successfully.

## Sprint retrospective

Complete when closing the sprint:

- What worked: deterministic, catalog/template-driven "natural conversation" (grouped
  questions, multi-fact extraction, shared NLU helpers) scaled to Spanish LOB-aware Claims
  without touching architecture principle #2; live DEV validation against the real deployment
  again surfaced defects (5) that the mock-provider-backed unit suite structurally could not —
  the same pattern PBI-04-04 established, now confirmed twice.
- What did not: the `injuries_reported`/`third_parties_involved` combined yes/no question can
  still only capture one answer per message when both are stated ambiguously in the same
  sentence (pre-existing PBI-04-04 limitation, not revisited this PBI).
- Technical debt: none introduced; one long-standing bug (`current_agent` never updated after
  the first turn) was found and fixed as part of this PBI's own handoff work.
- Security findings: none — no secrets, no new external surface, no RBAC/networking change.
- Follow-up PBIs: a small ordered-clause parser for the injuries/third-parties combined
  question, if that residual gap is ever judged worth closing (see `decisions.md`, PBI-04-04
  entry, restated as still-accepted).

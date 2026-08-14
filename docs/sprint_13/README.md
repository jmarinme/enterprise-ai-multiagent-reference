# Sprint 13 — Multi-Agent Observability

## Objective

Add a production-ready, separate Multi-Agent Observability experience (`/observability`) —
business/agentic telemetry (intent, routing, tool usage, tokens, estimated cost, latency) for
every conversation and processing run — as an extension of the current architecture, without
redesigning or regressing the existing chat, authentication, ReAct, or deployment model.

## Scope

- [x] PBI-13-01 (Phase 1 — Core): correlation IDs, shared `ObservabilityService`/repository
      abstraction, run persistence, conversation aggregates, `all_authenticated` authorization,
      summary/conversation-list/conversation-detail/run-detail APIs, `/observability` dashboard
      + detail page, chat integration instrumentation, tests, documentation.

## Out of scope (this sprint)

- Phase 2 (deterministic quality signals, Operational Quality Score) — reserved fields exist
  (`RunRecord`/`ConversationSummary`), left `None`/unpopulated.
- Phase 3 (advanced filters, richer timeline, privacy/audit UX polish).
- Real OpenTelemetry/Application Insights instrumentation — confirmed provisioned-but-not-
  instrumented (see `docs/Architecture/observability.md` §11); standing it up is a materially
  separate PBI.
- Activating Entra App Roles — prepared (backend enforces `roles` mode, token `roles` claim
  parsed) but not activated; no App Registration change made.
- Any deployment/Bicep apply — IaC updated only, never deployed (see `decisions.md`).

## Deliverables

- [x] Correlation model: `message_id`/`run_id` generated at the API boundary; the
      already-generated `correlation_id` is now actually threaded into `AgentRequest` (a
      pre-existing gap this PBI fixed, not a new mechanism).
- [x] `ObservabilityService` (`src/observability/service.py`) + `ObservabilityRepository`
      Protocol with in-memory (default) and Cosmos (`OBSERVABILITY_STORE_PROVIDER=cosmos`)
      implementations, mirroring `ConversationRepository`'s existing pattern.
- [x] `ToolCallingOrchestrator.run()` gained an optional `on_event` observability hook — the
      existing ReAct loop is instrumented, not replaced or duplicated.
- [x] `GET /observability/{summary,conversations,conversations/{id},runs/{id}}` — server-side
      paginated/filtered, centrally authorized.
- [x] `/observability` + `/observability/conversations/:id` frontend routes (new
      `react-router-dom` dependency — none existed before), a KPI/table dashboard, and a
      three-pane conversation detail page; `Header` gained a nav link, shown only when
      `showObservabilityNav` is true.
- [x] Cost calculation from a versioned, empty-by-default price catalog
      (`configs/observability/pricing.json`) — unknown pricing shows "Unavailable", never zero.
- [x] PII masking, centralized access control (`all_authenticated` V1, `roles` prepared).
- [x] `ADR-0012` (persistence model), `docs/Architecture/observability.md`.
- [x] `ops/bicep/modules/cosmos-db.bicep` extended with the `observability_runs` container
      (offline-validated via `az bicep build`, never deployed).

## Acceptance criteria

See `validation.md` for the full evidence-backed accounting (backend tests, ruff, mypy,
frontend tests/build/lint, offline Bicep validation) and `decisions.md` for every deviation
from the original task framing (all disclosed, none silent).

## Dependencies

- `src/core/tool_calling/orchestrator.py` (PBI-02-04/PBI-12-04, ADR-0011) — the existing
  bounded ReAct loop this sprint instruments.
- `src/services/conversation_store/` (ADR-0004) — the pattern `src/services/observability_store/`
  mirrors.
- `apps/api/src/api/auth/` (PBI-11-01) — `AuthenticatedUser.user_id`/`roles` this feature reuses
  verbatim, never replaces.

## Risks

- Cross-partition Cosmos queries for the dashboard's conversation list/KPIs at V1 scale —
  accepted, documented in ADR-0012, with an explicit review trigger.
- `all_authenticated` V1 access mode is a real, new cross-user data-visibility surface — flagged
  explicitly to the user before implementation, proceeded per their own explicit spec.
- `OBSERVABILITY_STORE_PROVIDER=cosmos` path is unit-tested (mocked SDK client) but not
  validated against a real deployed Cosmos account — `dev.bicepparam` deliberately keeps it at
  `in_memory` until that validation happens.

## Deliverable Log

<!-- Append entries. Do not remove previous entries. -->

PBI-13-01 (Phase 1): Multi-Agent Observability core delivered — 2026-08-12. See files
created/modified in `validation.md`. 740 backend tests passing (was 700, +40), 42 frontend
tests passing (was 40, +2), `ruff`/`mypy` clean, frontend `tsc --noEmit`/`eslint`/`vite build`
clean, offline `az bicep build` clean for `main.bicep`/`cosmos-db.bicep`/all three
`.bicepparam` files. Zero regressions to existing chat/auth/ReAct behavior.

## Sprint validation

See `validation.md`.

## Sprint retrospective

The mandatory Section 0 repository inspection (four parallel research passes across frontend,
backend/auth, agents/ReAct, and persistence/observability) materially changed the delivered
design versus the task's own initial framing: no frontend router existed at all (had to add
`react-router-dom`, the first new frontend dependency since project inception); Application
Insights was confirmed provisioned-but-never-instrumented (so `trace_id` had to be built as an
honest alias of the existing `correlation_id`, not a real OTEL id); and the persistence design
evolved during implementation from "extend the `Conversation` document" to a fully separate
`observability_runs` container once the write-amplification/document-size cost of the former
became concrete — a smaller, safer change to the existing chat path than originally proposed,
disclosed in `decisions.md` rather than applied silently.

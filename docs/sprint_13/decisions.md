# Sprint 13 — Decisions

<!-- Append entries. Do not remove previous entries. -->

## 2026-08-12 — Persistence design evolved from "extend `Conversation`" to a fully separate `observability_runs` container

The findings report presented to the user before implementation proposed Option A: extend the
existing `Conversation` document with optional aggregate fields, plus one new dedicated
container for run telemetry. During implementation this was refined further: the
`Conversation`/`conversations` container is **not** touched at all — a `ConversationSummary`
document (aggregated run counts/tokens/cost) lives in the new `observability_runs` container
instead, alongside `RunRecord` documents, both partitioned by `/conversationId`. This is a
strictly smaller, safer change to the existing chat persistence path than originally proposed
(zero schema change to `conversations`, zero new method on `ConversationRepository`). See
ADR-0012 for the full rationale. Disclosed here as a legitimate design refinement during
implementation, not a silent deviation from what was reported to the user.

## 2026-08-12 — No `/api` prefix on the new routes

PBI-13-01 §19 specified `GET /api/observability/...` but also explicitly said "adapt prefixes
if the existing API uses another convention." Repository inspection confirmed this backend has
no `/api` prefix anywhere (`/chat`, `/conversations`, `/health` all live at root). The
observability routes follow the existing flat-root convention (`/observability/summary`, etc.)
instead — an explicitly anticipated adaptation, not a deviation requiring separate sign-off.

## 2026-08-12 — `react-router-dom` upgraded to 7.18.2 (not 6.x) after `npm audit` findings

No router existed in the frontend at all before this PBI. `react-router-dom@^6` was the initial
choice (matches this project's existing React 18 stack most conservatively), but `npm audit
--omit=dev --audit-level=high` — the same command the CI `SecurityScan` gate runs — reported 2
moderate-severity CVEs (GHSA-wrjc-x8rr-h8h6, GHSA-337j-9hxr-rhxg) affecting the entire
`react-router` 6.0.0–7.17.0 range; the fix requires 7.18.0+. Upgraded directly to
`react-router-dom@^7.18.2` (`npm audit` now reports 0 production vulnerabilities, matching the
pre-PBI baseline) rather than ship a newly-introduced, avoidable CVE. Only basic
`BrowserRouter`/`Routes`/`Route`/`Link`/`useParams`/`useLocation` APIs are used — stable across
v6/v7's "declarative" mode, so this did not require adopting v7's newer "framework mode"
data-loader APIs.

## 2026-08-12 — `OBSERVABILITY_ACCESS_MODE=all_authenticated` implemented as specified, flagged not blocked

PBI-13-01 §16 explicitly and repeatedly specifies that, in V1, every authenticated user (not
just staff) may view every conversation's business/agentic observability data — a real,
new cross-user data-visibility surface distinct from the main chat's own strictly per-user
`/conversations` scoping. This was flagged explicitly in the pre-implementation findings report
(not silently shipped) because it touches CLAUDE.md §2/§6's least-privilege principles, but
implemented as specified rather than blocked on further confirmation, since the task's own
spec is unambiguous and deliberately designed this way (roles mode prepared for later
tightening — see `docs/Architecture/observability.md` §13).

## 2026-08-12 — Application Insights/OpenTelemetry instrumentation intentionally not built

Repository inspection confirmed Application Insights is provisioned in Bicep with zero
Python-side instrumentation anywhere (no `opentelemetry-*` dependency in either
`pyproject.toml`). PBI-13-01 §18 itself instructs "implement only what is justified by the
current architecture" when this is the case. Standing up real OTEL/App Insights instrumentation
is a materially separate, cross-cutting undertaking (SDK wiring, exporter config, sampling) —
not attempted here. `trace_id` in the new data model is documented as an honest alias of the
already-real `correlation_id`, never a fabricated distinct identifier.

## 2026-08-12 — Pricing catalog shipped empty

`configs/observability/pricing.json` ships with zero price entries rather than a plausible-
looking but unverified `gpt-5-mini` price. This repository has no confirmed, current Azure
OpenAI price list for this deployment; PBI-13-01 §15 requires unknown pricing to display
"Unavailable," never a fabricated figure. Every cost figure in the dashboard will show
"Unavailable" until an operator adds a real, dated entry (documented schema/example in
`docs/Architecture/observability.md` §7).

## 2026-08-12 — `OBSERVABILITY_STORE_PROVIDER` stays `in_memory` in `dev.bicepparam`

The Cosmos-backed `ObservabilityRepository` implementation is unit-tested (mocked SDK client,
same convention as the existing `CosmosConversationRepository` tests) but has not been
validated against a real deployed Cosmos account. `ops/bicep/modules/cosmos-db.bicep`
provisions the `observability_runs` container unconditionally (harmless, serverless, no
standing cost), but `dev.bicepparam` deliberately leaves `observabilityStoreProvider =
'in_memory'` rather than silently activating an unvalidated Azure-dependent code path in the
deployed DEV environment.

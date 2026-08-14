# Sprint 13 — Implementation Plan

## Phase 1 (delivered)

1. **Repository inspection** (mandatory, PBI-13-01 §0) — four parallel research passes:
   frontend/auth, backend API/auth/config, agents/Supervisor/ReAct/tools,
   persistence/observability infrastructure. Findings reported to the user before any code
   change.
2. **Domain models** — `src/domain/observability.py` (`RunRecord`, `RunToolCall`,
   `RunTokenUsage`, `ConversationSummary`, `SummaryKpis`), `src/domain/observability_repository.py`
   (Protocol).
3. **Persistence** — `src/services/observability_store/{in_memory,cosmos,factory}.py`, mirroring
   `src/services/conversation_store/` exactly. `src/config/settings.py`:
   `ObservabilityStoreSettings`, `ObservabilitySettings`.
4. **Pricing** — `src/observability/pricing.py` (`PricingCatalog`), `configs/observability/
   pricing.json` (shipped empty, deliberately — see `decisions.md`).
5. **PII masking** — `src/observability/masking.py`.
6. **ObservabilityService** — `src/observability/service.py`: builds a `RunRecord` from an
   `AgentResponse` + collected `ReActEvent`s, persists best-effort (never raises).
7. **ReAct instrumentation** — `src/core/tool_calling/models.py` (`ReActEvent`,
   `ReActEventSink`, `LLMUsageTotal`), `src/core/tool_calling/orchestrator.py` (optional
   `on_event` param, `usage`/`model` accumulation) — additive only, zero behavior change for
   every existing caller (verified: 700/700 pre-existing tests still pass unmodified except one
   test double's signature).
8. **Cross-cutting plumbing** — `AgentRequest.message_id`, `AgentResponse.model`/`token_usage`
   (`src/supervisor/models.py`); `Agent` Protocol gains `on_react_event`
   (`src/supervisor/registry.py`); `SupervisorOrchestrator.handle()`/`_persist_turn` forward it
   (`src/supervisor/orchestrator.py`); all four agents (`ClaimsAgent`, `BrokerAgent`,
   `CommercialIntakeAgent`, `FallbackAgent`) updated identically.
9. **Auth** — `AuthenticatedUser.roles` + token `roles` claim parsing (inert until Entra App
   Roles exist — see `docs/Architecture/observability.md` §13); `Settings.
   observability_access_mode`/`observability_allowed_roles`
   (`apps/api/src/config/settings.py`); `api.observability_access.require_observability_access`
   dependency.
10. **API** — `apps/api/src/api/routes/observability.py` (4 endpoints), registered in `main.py`
    behind `OBSERVABILITY_ENABLED`; `apps/api/src/api/dependencies.py` wiring
    (`get_observability_repository_dep`, `get_pricing_catalog`, `get_observability_service`).
11. **Chat integration** — `apps/api/src/api/routes/chat.py`: generates `message_id`/`run_id`,
    threads `correlation_id` (fixing a pre-existing gap — see `decisions.md`), collects
    `ReActEvent`s, calls `ObservabilityService.record_run` best-effort on both success and
    exception paths (re-raising the original exception unchanged on failure).
12. **Frontend** — added `react-router-dom` (upgraded to 7.18.2+ after `npm audit` flagged
    6.x/7.0-7.17 as vulnerable — see `decisions.md`); `App.tsx` restructured (`Header` hoisted
    to a shared `AuthenticatedApp` shell, `ChatApp`'s own rendered UI unchanged); `Header.tsx`
    gained a nav link; `api/observability.ts` client; `pages/ObservabilityDashboardPage.tsx`,
    `pages/ObservabilityConversationDetailPage.tsx`, `pages/observability.css`.
13. **Infrastructure (not deployed)** — `ops/bicep/modules/cosmos-db.bicep`
    (`observability_runs` container), `ops/bicep/main.bicep` (params, env vars, outputs),
    `ops/bicep/parameters/dev.bicepparam` (`observabilityStoreProvider = 'in_memory'`
    deliberately). Offline-validated via `az bicep build`/`build-params`.
14. **Tests** — 40 new backend tests across 6 new files + 1 stub-signature fix in an existing
    file; 2 new frontend tests (Header nav visibility).
15. **Documentation** — `ADR-0012`, `docs/Architecture/observability.md`, this sprint folder.

## Phase 2/3 (deferred — see `docs/Architecture/observability.md` §12)

Not started. Reserved schema fields (`operational_quality_score`, `business_outcome`) exist and
are `None` in every Phase 1 run/summary.

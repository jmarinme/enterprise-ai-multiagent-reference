# Sprint 13 — Validation

Commands actually executed, against a repo checkout on branch `feature/multiagent-observability`.

## Backend

```
python -m pytest tests/ -q --cov=src --cov=apps/api/src --cov-report=term
```
Result: **740 passed, 2 skipped, 0 failed** (was 700 passed/2 skipped before this PBI; +40 new
tests, 1 pre-existing test file's stub-agent signature updated to match the extended `Agent`
Protocol — no assertion changed). Coverage: 92% (`TOTAL`).

```
python -m ruff check apps/api/src src tests ops/scripts
```
Result: **All checks passed.**

```
python -m mypy apps/api/src
python -m mypy src
```
Result: **Success: no issues found** (22 and 136 source files respectively).

## Frontend

```
npx tsc --noEmit          # exit 0
npx eslint .               # exit 0, no output
npx vitest run             # 8 test files, 42 passed (was 40; +2 Header nav-visibility tests)
npm run build               # tsc --noEmit && vite build — succeeded
```

## Infrastructure (offline syntax only — never deployed)

```
az bicep build --file ops/bicep/main.bicep --stdout                       # exit 0
az bicep build --file ops/bicep/modules/cosmos-db.bicep --stdout          # exit 0
az bicep build-params --file ops/bicep/parameters/dev.bicepparam --stdout      # exit 0
az bicep build-params --file ops/bicep/parameters/staging.bicepparam --stdout  # exit 0
az bicep build-params --file ops/bicep/parameters/prod.bicepparam --stdout     # exit 0
```

No `az deployment` command was run. No Azure resource was created, modified, or queried against
a live subscription during this PBI.

## Files created

Backend (`src/`, `apps/api/src/`):
- `src/domain/observability.py`, `src/domain/observability_repository.py`
- `src/services/observability_store/{__init__,in_memory,cosmos,factory}.py`
- `src/observability/{service,pricing,masking}.py`
- `apps/api/src/api/observability_access.py`
- `apps/api/src/api/routes/observability.py`
- `configs/observability/pricing.json`

Frontend (`apps/web/src/`):
- `api/observability.ts`
- `pages/{ObservabilityDashboardPage.tsx,ObservabilityConversationDetailPage.tsx,observability.css}`

Tests:
- `tests/unit/observability/{test_pricing,test_masking,test_service}.py`
- `tests/unit/services/test_observability_store_in_memory.py`
- `tests/unit/api/{test_observability_access,test_observability_routes,
  test_chat_correlation_id_observability}.py`
- `tests/unit/core/tool_calling/test_react_events.py`

Documentation:
- `docs/Architecture/adr/0012-observability-persistence-model.md`
- `docs/Architecture/observability.md`
- `docs/sprint_13/{README,implementation-plan,validation,decisions}.md`

## Files modified

Backend: `src/config/settings.py`, `src/core/tool_calling/models.py`,
`src/core/tool_calling/orchestrator.py`, `src/supervisor/{models,registry,orchestrator}.py`,
`src/agents/{claims_agent,broker_agent,commercial_intake_agent,fallback_agent}.py`,
`apps/api/src/api/auth/{models,validator}.py`, `apps/api/src/config/settings.py`,
`apps/api/src/api/dependencies.py`, `apps/api/src/api/routes/chat.py`, `apps/api/src/main.py`.

Frontend: `apps/web/package.json` (added `react-router-dom`), `apps/web/src/App.tsx`,
`apps/web/src/components/Header.tsx`, `apps/web/src/config/env.ts`.

Tests (updated, not created): `tests/unit/supervisor/test_orchestrator.py` (stub agent
signature), `apps/web/src/components/Header.test.tsx` (Router wrapper + new prop).

Infrastructure: `ops/bicep/modules/cosmos-db.bicep`, `ops/bicep/main.bicep`,
`ops/bicep/parameters/dev.bicepparam`.

## Regression scope confirmed

- `git diff --stat` on every file listed above reviewed manually; no unrelated file touched.
- Zero changes to: JWT/JWKS validation logic, Cosmos `conversations` container schema,
  `ConversationRepository` methods/behavior, ReAct loop control flow (only an optional,
  default-`None` observer hook added), CORS/middleware configuration, Bicep resources other
  than the additive `observability_runs` container.

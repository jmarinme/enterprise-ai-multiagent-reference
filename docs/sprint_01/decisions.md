# Sprint 01 Decisions and Deviations

Record sprint-specific decisions and deviations. Cross-sprint decisions belong in ADRs.

## 2026-08-07 — PBI-01-01: Docker build context widened to repo root for `apps/api`

**Decision:** `apps/api/src/main.py` now depends on the shared, reusable `src/` package (`src.supervisor`, `src.agents`, `src.domain`, `src.services`) for the first time. The existing Docker build context (`./apps/api`, set in PBI-00-02/00-03) has no visibility outside that directory, so the image would not have contained `src/` at all. Changed `docker-compose.yml`'s `api` service to `context: .` / `dockerfile: apps/api/Dockerfile`; the Dockerfile now copies `apps/api/src` to `/app/app_src` (kept importable as bare `main`/`api`/`config`/`observability` via `--app-dir`) and repo-root `src/` to `/app/src` (importable as `src.*` via `ENV PYTHONPATH=/app`). Replaced `apps/api/.dockerignore` (no longer read, since the build-context root moved) with a new repo-root `.dockerignore`.

**Deviation/status change:** A necessary correction to keep this PBI's own deliverable (`POST /chat`) actually deployable, not a deviation from prior guidance — treated as a prerequisite per explicit user instruction, not scope creep. `apps/web`'s build context and Dockerfile are unaffected.

**How to apply:** Any future top-level `src/` subpackage the API needs will already be visible under `/app/src` in the image — no further Dockerfile changes needed unless a new *runtime* dependency (e.g. `azure-cosmos` if `CONVERSATION_STORE_PROVIDER=cosmos` is ever used in a deployed API container) needs adding to the `pip install` step, which it does not yet (default `in_memory`/`environment` providers need nothing extra).

## 2026-08-07 — PBI-01-01: added a 4th mock agent (`FallbackAgent`) for the `UNKNOWN` intent

**Decision:** The PBI explicitly requested three mock agents (Claims, Broker, Commercial Intake). A `FallbackAgent` was added and registered for `IntentCategory.UNKNOWN` so the `AgentRegistry` has a deterministic entry for every intent the rule-based resolver can produce, keeping `SupervisorOrchestrator.handle()` fully registry-driven — no special-casing "no agent found" for `UNKNOWN` specifically, and no unhandled `AgentNotFoundError` for ordinary unmatched chat input (e.g. "hello").

**Deviation/status change:** A small, deliberate addition beyond the literal 3-agent list, flagged explicitly rather than silently included. Still a deterministic, no-business-logic mock agent, consistent with every constraint the PBI placed on the other three.

**How to apply:** Any future intent category added to `IntentCategory` should have a registered agent (real or fallback) before being wired into the resolver, to preserve the "always resolvable, no branching" registry property this decision established.

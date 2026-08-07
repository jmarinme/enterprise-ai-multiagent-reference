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

## 2026-08-07 — PBI-01-02: branch cut before PBI-01-01 was merged to `main`; resolved via fast-forward merge

**Decision:** `feat/pbi-01-02-tool-framework` was created from `main` before `feat/pbi-01-01-supervisor-agent` (already committed) had been merged. At the start of PBI-01-02, `src/supervisor/`, `src/agents/`, `apps/api/src/api/dependencies.py`, `chat.py`, and the Docker build-context fix were all absent from the branch despite PBI-01-01 being marked complete in `docs/sprint_01/README.md`. Verified via `git merge-base HEAD feat/pbi-01-01-supervisor-agent` that the current branch tip *was* the merge-base (i.e., a pure fast-forward, zero divergence, zero conflict risk), then ran `git merge feat/pbi-01-01-supervisor-agent --ff-only`, which succeeded cleanly (32 files, no conflicts) before any PBI-01-02 code was written.

**Deviation/status change:** Not a code deviation — a repository/branch-topology issue, the same class already documented for PBI-00-01/00-02 in `docs/sprint_00/decisions.md`. Nothing was lost, discarded, or reverted; this was purely a not-yet-merged-branch situation caught and fixed before work began.

**How to apply:** Before starting a PBI whose scope explicitly builds on a previous PBI's files (as PBI-01-02's instructions explicitly did, listing `src/supervisor`, `src/agents`, `apps/api/src/api/dependencies.py` as inspection targets), verify those files actually exist on the current branch first — do not assume a prior PBI being "complete" in sprint docs means its commit is reachable from the branch in hand.

## 2026-08-07 — PBI-01-02: `ToolResult` generic kept as `Generic[T]`, not PEP 695 syntax

**Decision:** `ruff` (configured `target-version = "py312"`) flagged `class ToolResult(BaseModel, Generic[ToolOutputT]):` with `UP046`, recommending Python 3.12's newer `class ToolResult[ToolOutputT](BaseModel):` syntax. That syntax is a `SyntaxError` on Python 3.11, the only interpreter available to actually import/run/test this code in this environment (pre-existing R-01 gap, documented since Sprint 00). Kept the portable `Generic[T]` form — fully correct and supported on 3.12 too — and suppressed the rule locally with `# noqa: UP046` plus an inline comment explaining why.

**Deviation/status change:** A pragmatic, explicitly-justified rule suppression, not a quality-gate weakening — `ruff check` is still clean overall, and the suppression is scoped to the one line it applies to, not a blanket repo-wide ignore.

**How to apply:** Revisit this suppression once the local/CI Python interpreter gap (R-01) is actually closed (Python 3.12 installed) — at that point PEP 695 syntax becomes safe to adopt and the `noqa` can be removed. Any other generic class added before then should follow the same `Generic[T]` + justified `noqa` pattern for consistency.

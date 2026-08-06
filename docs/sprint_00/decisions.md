# Sprint 00 Decisions and Deviations

Record sprint-specific decisions and deviations. Cross-sprint decisions belong in ADRs.

## 2026-08-05 — Git risk resolved; repository connected to GitHub

**Decision:** Git is confirmed installed (`2.55.0.windows.3`). The repository has been initialized locally, an initial commit was created, and it has been pushed to the GitHub remote `origin` at https://github.com/jmarinme/enterprise-ai-multiagent-reference. Local `main` tracks `origin/main`.

**Deviation/status change:** The previously identified technical risk "Git not installed / repository not under version control" is closed. The `CLAUDE.md` §15 branch-per-PBI and commit workflow can now be followed for subsequent PBIs.

**Scope note:** This update is documentation-only. No PBI has been implemented or marked complete as part of this change.

## 2026-08-05 — PBI-00-01: no deviations found

**Decision:** PBI-00-01 (repository structure and Starter Kit validation) was executed and closed with no deviations. All 41 required directories and all 8 Starter Kit foundation files were already present and compliant with `CLAUDE.md` §6; `ops/scripts/init_structure.ps1` ran with 0 created directories, 0 placeholders, 0 failures.

**Deviation/status change:** None. Recorded here for audit traceability only, per `CLAUDE.md` §12 deviation-logging requirement.

## 2026-08-06 — Branch topology note: PBI-00-01 completion commit not reachable from this branch

**Observation:** `feat/pbi-00-02-api-foundation` (and `main`) currently point at commit `7806daa` ("docs(sprint-00): record Git and GitHub initialization"). A later commit, `4b21a3f` ("docs(sprint-00): complete PBI-00-01 repository validation"), exists in the local repository object database but is not reachable from any branch — `main` was not advanced to it before this feature branch was cut. As a result, `docs/sprint_00/README.md`/`validation.md`/`decisions.md` on this branch do not show the PBI-00-01 checkbox/log/evidence.

**Deviation/status change:** None applied here — this is a report of existing branch state, not a fix. Rewriting branch history (rebase, cherry-pick, or resetting `main`) is a git operation with irreversible-risk characteristics and was not performed without explicit authorization. PBI-00-02 work proceeds on top of the current branch state per explicit instruction to execute PBI-00-02 only.

**How to apply:** Before closing Sprint 00, reconcile branches so `4b21a3f`'s PBI-00-01 evidence is reachable from `main` (e.g., merge or cherry-pick), otherwise the sprint's git history will not reflect that PBI-00-01 was completed. Note: this merge (main → feat/pbi-00-02-api-foundation) has now brought the PBI-00-01 documentation into this branch directly, so the immediate documentation-visibility gap is resolved by this merge; the underlying `main` branch pointer / dangling-commit history question may still warrant cleanup.

## 2026-08-06 — PBI-00-02: Python interpreter version deviation

**Decision:** `apps/api/pyproject.toml` declares `requires-python = ">=3.12"` per `CLAUDE.md` §5, matching the target runtime. Local validation (pytest, ruff, mypy, and the runtime smoke test) was executed using the only interpreter available in this environment, Python 3.11.9, inside an isolated venv at `apps/api/.venv`.

**Deviation/status change:** This is the same pre-existing environment gap recorded 2026-08-05 (R-01 in `docs/sprint_00/implementation-plan.md`). No 3.12-only language features were used in the code written for PBI-00-02, so the 3.11.9 validation results are expected to hold under 3.12, but this has not been confirmed on the actual required interpreter. Marked as a known condition, not a blocker.

**How to apply:** Install Python 3.12 and re-run `pytest`/`ruff`/`mypy` against it before this code is considered fully compliant with `CLAUDE.md` §5, ideally before Sprint 00 closes.

## 2026-08-06 — PBI-00-03: `VITE_API_URL` moved from Compose `environment` to `build.args`

**Decision:** The pre-existing `docker-compose.yml` set `VITE_API_URL` under the `web` service's `environment:` key. Vite inlines `import.meta.env.VITE_*` variables into the JavaScript bundle at **build time** (`vite build`), not at container runtime — so a runtime `environment:` entry has no effect on an already-built static bundle. Changed to `build.args.VITE_API_URL`, and `apps/web/Dockerfile` declares a matching `ARG VITE_API_URL` / `ENV VITE_API_URL=$VITE_API_URL` set before `RUN npm run build`.

**Deviation/status change:** This is a correction of an existing starter-kit file, not new scope. Verified via `docker compose config` (resolves correctly) and via a local `vite preview` smoke test showing the built bundle contains the correct inlined URL.

**How to apply:** Any future change to how the Web app reaches the API (e.g., a different API host per environment) must be passed as a Compose/Bicep **build arg**, not a runtime environment variable, as long as the app is a statically-built Vite SPA.

## 2026-08-06 — PBI-00-03: frontend unit tests co-located under `apps/web/src`, not root `tests/`

**Decision:** `CLAUDE.md` §6 lists a single root `tests/{unit,integration,e2e,conversational}` tree, which PBI-00-02 used for `apps/api` Python unit tests (pytest). For the Web app, TypeScript/Vitest tests were instead co-located next to their source files under `apps/web/src` (`*.test.ts(x)`), following standard Vite/Vitest convention, keeping `apps/web` a self-contained, independently testable/deployable app like `apps/api`.

**Deviation/status change:** Minor structural deviation from a literal reading of `CLAUDE.md` §6's single root `tests/` tree (which is Python/pytest-oriented per §11's coverage-target wording). No repository top-level folder was added or renamed; this only affects where files live inside the existing `apps/web` folder.

**How to apply:** Keep Vitest/RTL tests co-located under `apps/web/src` for future PBIs touching the frontend; keep Python tests under root `tests/`, per PBI-00-02's precedent.

## 2026-08-06 — PBI-00-03: accepted dev-only npm audit findings (esbuild/vite chain)

**Decision:** `npm install` in `apps/web` reports 5 vulnerabilities (3 moderate, 1 high, 1 critical), all transitive from `esbuild <=0.24.2` (GHSA-67mh-4wv8-2f99), pulled in by `vite`/`vitest`/`vite-node`/`@vitest/mocker`. The advisory is specific to the Vite **development server** accepting arbitrary cross-origin requests; it does not affect the production build output served by `apps/web/Dockerfile` (`vite preview` over static `dist/` files, dev server never runs in the image). A fix requires a breaking major upgrade to `vite@8`.

**Deviation/status change:** Accepted as a known, non-blocking condition for Sprint 0 rather than performing an unplanned breaking dependency upgrade outside this PBI's scope.

**How to apply:** Re-evaluate before any environment exposes the Vite dev server beyond localhost (it should never be exposed in Container Apps/Azure), and revisit the vite major-version upgrade in a dedicated PBI/ADR if the advisory scope changes.

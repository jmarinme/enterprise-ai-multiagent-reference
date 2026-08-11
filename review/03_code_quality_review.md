# 03 — Code Quality Review

## 4a. Code standards

- **Linting/formatting**: `ruff` (backend) and `eslint` (frontend) are both configured and
  **enforced as hard CI gates**, not advisory — `azure-pipelines.yml`'s `BackendQuality` stage
  runs `ruff check apps/api/src src tests ops/scripts` then `mypy` on both `apps/api/src` and
  `src`; `FrontendQuality` runs `npm run lint` then `npm run typecheck` then the Vitest suite.
  Confirmed both gates are real (not soft-fail) by the stage structure — no `continueOnError`
  found on either lint/typecheck step.
- **No pre-commit hook** exists (`.pre-commit-config.yaml` absent) — lint/type errors are only
  caught at CI time (or manually), not before a commit is made locally. LOW-impact given CI
  already gates the merge, but a slower feedback loop than pre-commit would give.
- **`[tool.ruff]` config is minimal**: only `line-length`/`target-version` set, no explicit
  `[tool.ruff.lint] select=[...]` — meaning ruff runs its own default rule set (pyflakes +
  a small pycodestyle subset), **not** an extended set that would catch cyclomatic complexity
  (`C901`), unused-import-adjacent issues beyond the default, or stricter style rules
  (`ALL`/`E`/`W`/`I`/`UP` families). This repository's actual code quality is high regardless
  (verified throughout this session's own extensive direct reading), but the *enforced floor* is
  lower than the codebase's *actual* quality — a gap between "what's enforced" and "what's
  achieved by discipline," worth tightening.
- **Naming/function size**: consistently meaningful names, small single-purpose functions
  throughout every module read this session (dict-dispatched handler functions in
  `src/agents/*/workflow.py` are each one status transition, typically under 30 lines).
- **`mypy` is strict-leaning**: `disallow_untyped_defs = true`, `no_implicit_optional = true`,
  `warn_unused_ignores = true` — a genuinely strict configuration, not a token gesture, and
  confirmed clean (`Success: no issues found`) as recently as this session's own PBI-09-01 work.

## 4b. Error handling

- **Explicit, never silently swallowed**: every multi-turn Agent (`ClaimsAgent`, `BrokerAgent`,
  `CommercialIntakeAgent`) has exactly one documented broad `except Exception` boundary at its
  outermost `handle()` call, with an explicit code comment justifying why (the boundary between
  the deterministic state machine and the "never leak a stack trace to the user" guarantee) —
  verified as a consistent, deliberate pattern across all three, not an accident of copy-paste.
- **User-facing error messages are safe**: the broad-catch fallback always returns a fixed,
  bilingual, generic message (`_SAFE_FALLBACK_MESSAGE`) — never the exception's own text, never a
  stack trace, never an internal path. Verified by reading the exact `except` blocks in all three
  `*_agent.py` files.
- **No global unhandled-exception/promise handler was found on the frontend** (`apps/web/src/`) —
  a gap if an unexpected render-time error occurs; not independently confirmed as causing a
  visible problem, but no React error boundary was found in a scan of `apps/web/src/`.
- **No bare `except:`** found anywhere (`grep -rn "except:" src/ apps/api/src/` — zero hits);
  every catch clause names its exception type(s) explicitly, consistent with CLAUDE.md §9's own
  "no bare except" rule.

## 4c. Test coverage

- **93 test files**, spanning `tests/unit/` (the large majority), `tests/integration/`,
  `tests/e2e/` (1 file, added since the prior review — a lightweight concurrency/load smoke
  test), and `tests/conversational/` (3 files, added since the prior review — prompt-injection/
  adversarial-input scenarios plus this review's own immediate predecessor's live-conversation
  regression suite).
- **Exact current pass count** (this session's own final run, PBI-09-01): **649 passed, 2
  skipped**, zero failures — independently re-run and confirmed as part of this session's work
  immediately preceding this review, not an assumed/stale number.
- **No coverage percentage is measured** — no `pytest-cov`/`coverage.py` dependency exists in
  either `pyproject.toml`. CLAUDE.md §11 states a 70% target but nothing in CI actually measures
  or gates on it — the target is aspirational/unenforced, not verified. This is a real
  measurement gap, independent of whether actual coverage is adequate (the sheer test-to-code
  ratio and the deliberate "every Tool requires contract tests, every agent requires routing
  tests" discipline evidenced throughout the sprint logs suggests it likely is adequate, but this
  review cannot state a number).
- **Critical paths are tested, including live-system paths, not just mocked unit tests**: the
  `tests/conversational/` suite exercises real multi-turn flows through the actual FastAPI app
  (`TestClient` + `MockLLMProvider`, not a stub); `tests/e2e/test_load.py` exercises 20 concurrent
  real HTTP requests through the actual app. This closes the prior review's own top-5 finding
  ("conversational/E2E regression protection is manual, not automated") — automated coverage now
  exists where none did before.
- **Tests read as meaningful, not coverage padding**: sampled test names/bodies throughout this
  session consistently assert specific business outcomes ("policy already resolved is never
  re-asked," "a bare 'no' answering the combined question resolves both fields") rather than
  trivial "does not throw" assertions — a good sign the suite would actually catch a regression.

## 4d. Dependency health

- **Backend**: range-pinned (`>=x,<y`), not exact-pinned, **no lockfile** (repeat of the
  Architecture/Security reviews' own finding — this is the single dependency-health gap in an
  otherwise clean picture). Practical impact: two CI runs on different days could theoretically
  resolve different patch versions within the same range — low risk given the small, current
  dependency set, but a real reproducibility gap.
- **Frontend**: `package-lock.json` present and committed — exact, reproducible resolution.
- **No duplicate/unnecessary dependencies observed** — both `pyproject.toml` files and
  `package.json` list a small, clearly-justified set (each with an inline comment explaining why
  it's needed, e.g. `apps/api/Dockerfile`'s own commentary on why `aiohttp`/`azure-cosmos` are
  installed unconditionally).
- **No abandoned dependency** identified — every direct dependency (FastAPI, Pydantic, React,
  Vite, Azure SDKs) is an actively-maintained, mainstream package.
- **Dev dependencies do not leak into the production image**: `apps/api/Dockerfile` explicitly
  installs only the runtime package list (`fastapi`, `uvicorn`, `pydantic`, etc.) — `pytest`,
  `ruff`, `mypy` are never `pip install`ed inside the image, confirmed by direct read of the
  Dockerfile's own `RUN pip install` step. The frontend image runs `npm ci` (installs
  devDependencies too, needed for the Vite build step) then `npm run build` — devDependencies are
  present in the *build* stage but the image is single-stage, so the final runtime image (a
  single-stage Node image running `npm run preview`) does carry `node_modules` including
  devDependencies at runtime, unlike a proper multi-stage build that would discard them. Minor
  image-bloat/attack-surface concern, not a functional one.

## 4e. Build & deployment pipeline

- **CI/CD is mature and real**, not aspirational: `azure-pipelines.yml` (reviewed in full this
  session across several PBIs) implements Quality (Backend+Frontend, parallel) → SecurityScan
  (parallel) → ContainerBuildValidation (feature branches only) → Build → InfrastructureDeploy
  (quota-aware, isolated from the Deploy stage) → Deploy DEV → Smoke Tests, with real evidence
  artifacts published at each stage.
- **Environment-specific config is cleanly separated from code**: `.bicepparam` files per
  environment, `Settings` (Pydantic Settings) reading env vars, nothing environment-specific
  hardcoded in application source — verified by grep (no `"dev"`/environment-name string
  literals found gating business logic in `src/`).
- **Production build reproducibility**: container images are tagged with a build-traceable,
  timestamped+PBI-suffixed tag (e.g. `dev-20260811024920-pbi0901`, this session's own build),
  never `latest` — good practice, independently confirmed via this session's own live `az acr
  build`/`az containerapp update` deployment. The *dependency resolution* inside that image is
  still not exactly reproducible build-to-build (repeat of 4d's lockfile gap) even though the
  *image tag* itself is.

## Summary count (feeds `04_risk_register.md`)

| Severity | Count |
|---|---|
| HIGH | 0 |
| MEDIUM | 2 (no coverage measurement/gate; no Python dependency lockfile — already counted once in Security, cross-referenced not double-counted in the register) |
| LOW | 4 (no pre-commit hooks, minimal ruff rule set, no frontend error boundary, dev deps present in the single-stage web runtime image) |
| INFO | 1 (zero TODO/FIXME/HACK debt — a positive finding) |

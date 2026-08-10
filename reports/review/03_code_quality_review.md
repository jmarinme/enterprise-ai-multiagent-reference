# 03 — Code Quality Review

Reviewer persona: Engineering Lead. Scope: standards enforcement, error handling, test coverage,
dependency health, build/deploy pipeline.

## 4a. Code standards

**Finding CQ-01 (positive, verified):** Both `pyproject.toml` (root) and `apps/api/pyproject.toml`
declare `[tool.ruff]` (`line-length = 100`, `target-version = "py312"`) and `[tool.mypy]`
(`disallow_untyped_defs = true`, `warn_unused_ignores = true`, `no_implicit_optional = true`) —
a genuinely strict mypy configuration, not a token gesture. `azure-pipelines.yml:178-190` runs
both (`ruff check`, `mypy`) as separate, independently-failing quality-gate steps in
`BackendQuality`, each with `set -e` so any failure stops the job (no `continueOnError`
anywhere in the reviewed pipeline). The frontend mirrors this: `apps/web/package.json:11`
(`"typecheck": "tsc --noEmit"`) plus ESLint 9 + `typescript-eslint` 8, run in
`azure-pipelines.yml:244-250` (`FrontendQuality` stage). Every sprint's Deliverable Log entry
this review read explicitly states "ruff and mypy clean" / "tsc/eslint clean" as part of that
PBI's own completion evidence — this is enforced practice, not aspirational config.

**Finding CQ-02:** No pre-commit hook configuration (`.pre-commit-config.yaml`) exists — quality
gates run only in CI, not locally before commit. Low-impact given CI enforces them anyway before
merge, but it means a contributor's local iteration loop has no fast local gate and the stray
`tatus` file (see `01_architecture_review.md` A-16) is exactly the class of thing a
`pre-commit run --all-files` / simple `git status` hook would have caught before it reached a
commit.

## 4b. Error handling

**Finding CQ-03 (positive, verified pattern):** Every framework layer converts failures into
typed results/exceptions rather than leaking raw exceptions to callers — verified directly in
`src/tools/` (`ToolExecutor` "never raises to its caller — always returns a typed `ToolResult`,"
per `docs/sprint_01/README.md` AC-09, backed by a dedicated test
`tests/unit/tools/test_executor.py`), `src/prompts/` (`PromptManager` "normalizes unexpected
provider failures into typed `PromptValidationError`"), `src/rag/` (`KnowledgeRetriever` /
`Grounder` degrade gracefully — Claims Agent knowledge-retrieval failure "degrades gracefully...
never a raw exception or blocked response," per Sprint 02 AC-08 with its own regression test).
This is a consistent, deliberate architectural pattern applied uniformly across five different
frameworks, not an accident of one file.

**Finding CQ-04 (positive):** User-facing error messages are deliberately generic and safe.
`docs/sprint_04/README.md` AC-38 and its Deliverable Log confirm that technical details (prompt
versions, LLM model identifiers, tool names, tool failures, stack traces, internal IDs) are
explicitly stripped from the visible response text and moved into a metadata-only diagnostic
field (`AgentResponse.metadata["diagnostics"]`) never rendered in the chat UI — this is a real,
implemented safe-error-message pattern, not just a claim. The Web client's own error path
(`docs/sprint_04/README.md` PBI-04-02 Deliverable Log) uses "a generic safe error message with a
working Retry action (never a raw exception/status)."

**Finding CQ-05:** No global/centralized FastAPI exception handler (`@app.exception_handler`) was
observed in `apps/api/src/main.py:12-36` — the only explicit `HTTPException` usage found is a
single `404` in `conversations.py:104` for a missing conversation. This means an unhandled
exception anywhere in the request path (e.g. a Cosmos SDK exception not otherwise caught) would
currently surface as FastAPI's default 500 response, which in a default (non-`debug`) Starlette
configuration does not leak a stack trace to the client — so this is a low-severity gap (the
default behavior is already safe), but an explicit handler would make the "never leak internals"
policy an enforced invariant rather than an implicit consequence of Starlette's defaults.

## 4c. Test coverage

**Finding CQ-06 (quantitative):** 76 test files exist under `tests/`, distributed as:

| Directory | File count |
|---|---|
| `tests/unit/tools/` | 10 |
| `tests/unit/api/` | 8 |
| `tests/unit/agents/` (incl. `broker/`, `claims/`, `commercial/`, `shared/` subfolders) | 9 top-level + 12 in subfolders = 21 |
| `tests/unit/rag/` | 7 |
| `tests/unit/services/` | 6 |
| `tests/unit/llm/` | 5 |
| `tests/unit/pipelines/knowledge_ingestion/` | 5 |
| `tests/unit/supervisor/` | 4 |
| `tests/unit/core/tool_calling/` | 3 |
| `tests/unit/prompts/` | 3 |
| `tests/unit/domain/` | 1 |
| `tests/integration/` | 2 (`test_cosmos_conversation_repository.py`, `test_key_vault_live.py` — both designed to skip without real Azure credentials, per Sprint 00 deliverable logs) |
| `tests/e2e/` | **0** (only `.gitkeep`) |
| `tests/conversational/` | **0** (only `.gitkeep`) |

The final regression count reported in the most recent sprint (`docs/sprint_05/README.md` Sprint
validation section) is **551 backend tests passed, 2 skipped**, plus **33 frontend tests
passed**, both with clean lint/typecheck — this is a real, large, passing suite, and per-PBI
Deliverable Log entries throughout Sprints 01–05 consistently report growing, all-green counts
after every change (never a silently-reduced or skipped test count).

**Finding CQ-07 (real gap against CLAUDE.md §11):** CLAUDE.md §11 states "Every prompt change
requires conversational/evaluation tests" and "E2E tests when a complete business flow changes."
`tests/e2e/` and `tests/conversational/` contain **only** `.gitkeep` placeholder files — zero
actual tests — despite five sprints of prompt rewrites (Claims system prompt bumped 1.0.0→2.0.0
in PBI-01-05 alone), routing changes, and multiple complete business-flow changes (full Claims/
Broker/Commercial intake flows, Spanish-language rewrite in Sprint 04). The project's actual
practice substitutes **manual, human-driven live-DEV validation** (a real person or the
Claude Code session driving a real multi-turn conversation against the live deployed API, then
recording the transcript in `validation.md`) for automated conversational/E2E tests — this is
real, valuable validation (and per the sprint logs, it repeatedly caught defects the mocked unit
suite could not, e.g. `docs/sprint_04/README.md` PBI-04-02's Tool Calling message-sequencing bug,
and `docs/sprint_05/README.md`'s retrospective explicitly states "live DEV validation against the
real deployment again surfaced defects (5) that the mock-provider-backed unit suite structurally
could not... the same pattern PBI-04-04 established, now confirmed twice") — but it is **not
automated regression protection**. Nothing prevents a future change from silently breaking a
previously-validated live conversation flow between now and the next manual DEV validation pass.
This is the most concrete, well-evidenced code-quality gap in the repository: the pattern is
explicitly known to catch real bugs, is repeatedly relied upon, and yet is not captured as a
repeatable, automated test.

**Finding CQ-08 (positive):** Critical paths — routing (`tests/unit/supervisor/`), Tool
authorization/execution (`tests/unit/tools/`, `tests/unit/core/tool_calling/`), and the
confirmation gate before claim registration (per `docs/sprint_04/README.md` AC-43, "registration
only proceeds after 'sí, confirmo'," live-verified) — are exercised by real, meaningful tests, not
trivial smoke assertions, based on the specific test names cited throughout the Sprint 01/02/04
acceptance-criteria tables reviewed (e.g. `test_run_rejects_an_unauthorized_tool_call_without_
executing_it`, `test_run_stops_at_max_iterations_against_a_never_terminating_llm`) — these read
as genuine behavioral assertions, not `assert True`-style placeholders.

## 4d. Dependency health

**Finding CQ-09:** Both `pyproject.toml` files use open version ranges
(`fastapi>=0.115,<1`, `pydantic>=2.7,<3`, etc.) with no lockfile
(no `uv.lock`/`poetry.lock`/`requirements.txt` with pinned hashes) — builds are reproducible only
to the extent the range resolves consistently at install time, which is not guaranteed across
different install dates. `apps/web/package-lock.json` is present and correctly pins exact
versions — the frontend does not share this gap.

**Finding CQ-10:** No unnecessary or clearly duplicate dependencies were found — the optional-
extras structure in the root `pyproject.toml` (`cosmos`, `keyvault`, `azureopenai`, `azuresearch`,
`ollama`, `dev`) is a clean, minimal-surface pattern: each Azure SDK dependency is opt-in and
lazily imported by its corresponding provider (per the "lazy import" pattern documented
repeatedly across Sprint 01/02/03 deliverable logs), so a deployment that doesn't select
`LLM_PROVIDER=azure_openai` never needs `openai`/`azure-identity` installed at import time (though
the Dockerfile does install them unconditionally for the current DEV configuration, per
`apps/api/Dockerfile:34-44`'s own comment explaining why).

**Finding CQ-11:** `apps/api/Dockerfile:34-44` installs a specific, hand-maintained list of pip
packages directly in the `RUN pip install` line rather than installing from
`apps/api/pyproject.toml`'s own dependency list (which is `COPY`'d at line 34 but never actually
used by `pip install .`/`pip install -e .`) — this means the Dockerfile's dependency list and
`apps/api/pyproject.toml`'s declared dependencies can silently drift apart over time (they
happen to match today). A minor but real reproducibility/maintainability gap: two sources of
truth for "what does the API image need" where one (the `pyproject.toml` copy) is currently
unused dead weight in the image build.

## 4e. Build & deployment pipeline

**Finding CQ-12 (positive, thorough):** `azure-pipelines.yml` (651 lines, read in full) runs, in
order: pytest with coverage (`--cov=src --cov=apps/api/src`, JUnit + coverage XML published),
ruff, mypy (Stage 1); npm lint, typecheck, Vitest, production build (Stage 2); `az bicep build`/
`build-params` for every module and parameter file via reusable templates (Stage 3) — all three
running in parallel, all gating any later deploy stage. Deployment (Stages 4-8) is
branch-gated (`isDeployRun`, only `main`), uses dynamically-resolved resource names (no
hardcoded ACR/Container-App names beyond the one deliberately-fixed resource group name, per the
pipeline's own header comment), never re-runs `az deployment group create` for a routine deploy
(only a targeted `az containerapp update --image`), and includes real smoke tests
(`GET /health`, `POST /chat` with a JSON-shape assertion) that fail the pipeline on any non-2xx
or malformed response. This is a genuinely production-grade CD pipeline design for what it
covers.

**Finding CQ-13 (gap, cross-referenced from Security):** As noted in `02_security_review.md`
(SEC-08), no dependency or container image vulnerability scan step exists in any of the 8
stages. This is the pipeline's most significant missing quality gate relative to how thorough
everything else in it is.

**Finding CQ-14:** Environment separation exists in the IaC (`dev`/`staging`/`prod`
`.bicepparam` files, each with distinct SKU/scaling/networking defaults, per
`docs/sprint_00/README.md` PBI-00-04 and `docs/sprint_03/README.md` PBI-03-04) but the CI/CD
pipeline itself only targets `rg-tmx-agent-platform-dev` — no QA/staging/prod pipeline stage
exists yet. This is explicitly, correctly scoped out in `docs/sprint_04/README.md`'s own "Out of
scope" section ("Creating a QA or Production Azure DevOps environment... not listed") — a
documented gap, not an oversight, and consistent with CLAUDE.md's own statement that only DEV
exists today.

## Code quality review summary

| ID | Finding | Severity | Type |
|---|---|---|---|
| CQ-01 | Strict ruff/mypy config, enforced in CI on every push/PR, verified via sprint logs | — | Positive |
| CQ-02 | No pre-commit hooks — quality gates are CI-only | Low | Gap |
| CQ-03 | Consistent "typed result, never raise to caller" pattern across 5 frameworks | — | Positive |
| CQ-04 | User-facing errors are generic/safe by design, technical detail moved to hidden metadata | — | Positive |
| CQ-05 | No global FastAPI exception handler (relies on Starlette's safe default) | Low | Gap |
| CQ-06 | 551 backend + 33 frontend tests passing as of the latest sprint (quantitative, verified via sprint doc) | — | Positive |
| CQ-07 | `tests/e2e/`/`tests/conversational/` are empty; conversational/E2E regression protection is manual, not automated, despite CLAUDE.md §11 requiring it and the project's own logs showing manual validation repeatedly catches real bugs | Medium-High | Real, well-evidenced gap |
| CQ-08 | Critical paths (routing, tool authorization, confirmation gate) have meaningful, specific unit tests | — | Positive |
| CQ-09 | Python dependencies unpinned (no lockfile); frontend correctly pinned | Low | Gap |
| CQ-10 | Dependency extras are minimal and lazily imported — no bloat found | — | Positive |
| CQ-11 | API Dockerfile's pip-install list and `apps/api/pyproject.toml` are two independent sources of truth | Low | Gap |
| CQ-12 | CI/CD pipeline is thorough: tests, lint, type-check, IaC validation, gated deploy, real smoke tests | — | Positive |
| CQ-13 | No SCA/container vulnerability scanning in the pipeline | Medium | Gap (= SEC-08) |
| CQ-14 | Only DEV has a CD target; QA/Prod pipelines don't exist yet (documented, correct scope) | — | Documented, accepted |

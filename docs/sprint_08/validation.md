# Sprint 08 — Validation

All commands below were actually executed in this session, from the repository root, using the
project's `.venv`. No live Azure mutation, no `az deployment group create`, no `az containerapp
update`, no commit, no push.

## A-07 (Resilience) — targeted, during development

```
./.venv/Scripts/python.exe -m pytest tests/unit/core/resilience/ -v
```
Result: **11 passed** — `retry_with_backoff` (5 tests: first-attempt success, retry-then-
succeed, exhausts and raises, never retries a non-listed exception, `is_retryable` predicate
narrowing) and `CircuitBreaker` (6 tests: closed/stays-closed, opens at threshold, fails fast
without calling the operation, half-open trial success closes it, half-open trial failure
reopens it, stays open until the reset timeout elapses).

```
./.venv/Scripts/python.exe -m pytest tests/unit/llm/test_azure_openai_provider.py -k "retries or non_transient or circuit_breaker" -v
```
Result: **3 passed** — retries a transient timeout then succeeds (3 attempts); does not retry a
non-transient `APIStatusError` (1 attempt only); circuit breaker opens after 2 failures and
fails fast on the 3rd call without invoking the mocked SDK client again.

```
./.venv/Scripts/python.exe -m pytest tests/unit/rag/test_azure_ai_search_provider.py -v
```
Result: **18 passed** (15 pre-existing + 3 new: retry-then-succeed, no-retry-on-auth-failure,
circuit-breaker-opens).

```
./.venv/Scripts/python.exe -m pytest tests/unit/services/test_cosmos_conversation_repository_resilience.py -v
```
Result: **5 passed** — retry-then-succeed on a transient `ServiceRequestError`; a 404 returns
`None` on the first attempt (never retried); a 429 (RU throttling) retries then succeeds; a 409
(conflict) is never retried; the circuit breaker opens after 2 failures and fails fast (the
underlying `query_items` call is never invoked a 3rd time).

```
./.venv/Scripts/python.exe -m ruff check src/core/resilience/ src/llm/ src/rag/azure_ai_search_provider.py src/services/conversation_store/cosmos.py
./.venv/Scripts/python.exe -m mypy src
```
Result: both clean (`mypy`: "Success: no issues found in 124 source files").

## A-08 (Readiness) — targeted, during development

```
./.venv/Scripts/python.exe -m pytest tests/unit/api/test_health.py -v
```
Result: **6 passed** — `/health` unchanged (2 pre-existing tests); `/ready` returns `200`/
`"ready"` when every default (mock/in-memory/local) dependency is healthy; returns `503`/
`"degraded"` when the LLM is unreachable; never exposes the underlying exception message text in
the response body (a deliberately "leaky"-looking exception string was asserted absent);
`/ready` echoes `X-Correlation-ID` exactly like `/health` already does.

```
./.venv/Scripts/python.exe -m ruff check apps/api/src/api/routes/health.py src/llm/
./.venv/Scripts/python.exe -m mypy apps/api/src
```
Result: both clean (`mypy`: "Success: no issues found in 14 source files").

## A-11 (Monitoring) — Bicep, real Azure validation (non-mutating)

```
az bicep build --file ops/bicep/modules/monitor-alerts.bicep --stdout
```
Result: clean (after removing one initially-unused `location` parameter — every resource in
this module is global-scoped).

```
az bicep build --file ops/bicep/main.bicep --stdout
```
Result: clean — the new module compiles correctly wired into the full template.

```
az deployment group validate --resource-group rg-tmx-agent-platform-dev \
  --template-file ops/bicep/main.bicep --parameters ops/bicep/parameters/dev.bicepparam
```
Result: **`provisioningState: "Succeeded"`**, with `monitor-alerts-deployment` listed among
`validatedResources` — confirms the new `Microsoft.Insights/actionGroups`/`metricAlerts`
resources are genuinely schema-valid against real ARM, not just Bicep-compiler-valid.

```
az deployment group what-if --resource-group rg-tmx-agent-platform-dev \
  --template-file ops/bicep/main.bicep --parameters ops/bicep/parameters/dev.bicepparam \
  --result-format ResourceIdOnly
```
Result: **"Resource changes: 3 to deploy, 10 to ignore"** — zero resources marked for deletion
or replacement. The pre-existing `NestedDeploymentShortCircuited` limitation (documented in
`docs/sprint_06/validation.md`, caused by `containerAppsEnvironment`'s own `reference()`/
`listKeys()` usage) prevents what-if from itemizing exactly which 3 new resources the new
nested `monitor-alerts-deployment` would create — `validate`'s success above is the
authoritative, unaffected check, per this project's own established precedent.

```
az monitor metrics list-definitions --resource "appi-tmxap-dev" --resource-group rg-tmx-agent-platform-dev --resource-type "Microsoft.Insights/components"
az monitor metrics list-definitions --resource "ca-tmxap-dev-api" --resource-group rg-tmx-agent-platform-dev --resource-type "Microsoft.App/containerApps"
```
Result: confirmed live, real metric names before writing any alert rule — `requests/failed`,
`requests/duration` (Application Insights), `Replicas` (Container Apps) — none guessed.

## A-16 (Hygiene)

```
ls -la  (repository root)
git ls-files | grep -v "/"
```
Result: `tatus` confirmed present, tracked by git, containing a dumped `git diff` transcript
(matching `01_architecture_review.md`'s A-16 description exactly). Removed
(`rm tatus`). Every other root-level file (`.dockerignore`, `.editorconfig`, `.env.example`,
`.gitignore`, `CLAUDE.md`, `README.md`, `TMX_initialprompt_Sprint0.md`, `azure-pipelines.yml`,
`docker-compose.yml`, `pyproject.toml`) confirmed to be a legitimate, expected file — no other
accidental artifact found.

## A-17 (Hardening evidence)

```
./.venv/Scripts/python.exe -m pytest tests/conversational/ -v
```
Result: **7 passed** (system-prompt-extraction, fake-authority-claim-approval, SQL-injection-
shaped policy number, XSS-shaped message, extremely long message, role-override/bulk-dump
attempt, correlation-ID header/body separation).

```
./.venv/Scripts/python.exe -m pytest tests/e2e/ -v -s
```
Result: **2 passed** — 20 concurrent `POST /chat` requests: p50 0.094s, p95 0.094s, max 0.094s,
total wall-clock 0.096s, 20/20 succeeded (well within the deliberately generous bounds — see
`evidence/latency-and-cost-telemetry.md` for the full captured output including the real
`supervisor_turn_latency` structured-log lines this run produced); a second scenario (8 normal +
8 unknown-policy requests running concurrently) confirmed no cross-request state leakage — all
16 still returned `200`.

### Dependency/security scan evidence (Sprint 07's tooling, re-run for current state)

```
./.venv/Scripts/python.exe -m detect_secrets scan src apps/api/src apps/web/src ops configs tests --all-files
```
Result: **0 files flagged** — the exact scope the `SecurityScan` pipeline stage uses.

```
<isolated venv matching the SecurityScan stage's exact dependency list>/python.exe -m pip_audit \
  --progress-spinner off --format json -o <tmp> --ignore-vuln PYSEC-2026-1845
```
Result: **"No known vulnerabilities found, 1 ignored"** (the same documented, justified
pytest-9-only exception from Sprint 07 — `setuptools` was already upgraded in that venv).

```
cd apps/web && npm audit --omit=dev --audit-level=high
```
Result: **"found 0 vulnerabilities"**.

See `evidence/` for the raw captured output of all three.

### Full backend quality gate (matches azure-pipelines.yml's exact invocation)

```
./.venv/Scripts/python.exe -m ruff check apps/api/src src tests ops/scripts
./.venv/Scripts/python.exe -m mypy apps/api/src
./.venv/Scripts/python.exe -m mypy src
```
Result: all three clean.

## Final regression (after implementation was stable — run once, per this PBI's own instruction)

```
./.venv/Scripts/python.exe -m pytest tests/ -q
```
Result: **612 passed, 2 skipped** (the 2 skipped are pre-existing, unrelated to this PBI).

## Not performed (explicitly, per this PBI's own scope and CLAUDE.md §7.1)

- No `az deployment group create` — the new `monitor-alerts` Bicep module was validated
  (non-mutating) but not applied to real Azure; Azure DevOps owns deployment once CI/CD is
  operational.
- No `az containerapp update` — no application code was deployed to the live DEV Container App.
- No live Azure OpenAI/Cosmos/AI Search failure injection — resilience/readiness behavior is
  validated against fully mocked failures, matching this repository's existing testing
  convention throughout every prior sprint.
- No commit, no push.

## PBI-08-01A (feature-gate Azure Functions infrastructure) — 2026-08-10, later same-day session

```
az bicep build --file ops/bicep/main.bicep --stdout
```
Result (first pass): compiled with exit 0 but **8 `BCP318` warnings** ("may be null") on every
reference to `functionAppStorage.outputs.*`/`claimsToolsFunctionApp.outputs.*` from outside
their own now-conditional module blocks (a plain `deployServerlessToolLayer ? module.outputs.x
: ''` ternary does not suppress this — Bicep's null-analysis doesn't correlate a ternary
condition with a separate module's own `if()` condition, even when textually identical).

```
(same command, after converting every such reference to `.?outputs.?x ?? ''` safe-dereference,
plus one shared `claimsFunctionAppHostName`/`claimsFunctionAppUrl` var computed once)
```
Result: **exit 0, zero warnings.**

```
az bicep build-params --file ops/bicep/parameters/dev.bicepparam --outfile <tmp>
```
Result: exit 0 — `dev.bicepparam` (with the new `deployServerlessToolLayer = false` line)
resolves against `main.bicep`'s parameter contract.

```
az deployment group validate --resource-group rg-tmx-agent-platform-dev \
  --template-file ops/bicep/main.bicep --parameters ops/bicep/parameters/dev.bicepparam
```
Result: **`provisioningState: "Succeeded"`**. `validatedResources` (15 entries):
`id-tmxap-dev`, `log-tmxap-dev`, `ai-search-deployment`, `api-container-app-deployment`,
`app-insights-deployment`, `app-insights-secret-deployment`, `azure-openai-deployment`,
`container-apps-environment-deployment`, `container-registry-deployment`,
`cosmos-db-deployment`, `key-vault-deployment`, `log-analytics-deployment`,
`managed-identity-deployment`, **`monitor-alerts-deployment`**, `web-container-app-deployment`.
**Confirmed absent: `function-app-storage-deployment`, `claims-tools-function-app-deployment`**
— compared directly against the PBI-08-01 (pre-gating) `validate` run, whose
`validatedResources` list included both.

### Static deployment-plan inspection

```
az bicep build --file ops/bicep/main.bicep --outfile <tmp>/main_compiled.json
python -c "... inspect resources[].condition for names containing 'function-app' ..."
```
Result:
```
name: function-app-storage-deployment
condition: [parameters('deployServerlessToolLayer')]

name: claims-tools-function-app-deployment
condition: [parameters('deployServerlessToolLayer')]

name: monitor-alerts-deployment
condition: None
```
Confirms, independently of the live `validate` call, that both gated resources carry the
correct condition expression, and `monitor-alerts-deployment` (whose own internal `enabled`
param — default `true` — governs its 3 alert resources) is unaffected, gated at a different
level entirely.

## Not performed (explicitly, per this PBI's own scope)

- No `az deployment group create` — "Do NOT deploy yet" per this PBI's own explicit instruction.
- No `az deployment group what-if` — the pre-existing `NestedDeploymentShortCircuited`
  limitation (documented since Sprint 06) already prevents it from itemizing individual nested
  resources; `validate` (unaffected by that limitation) plus the static JSON inspection above
  together provide stronger, more precise evidence than `what-if` could add here.
- No commit, no push.

# Sprint 14 — Validation

All commands below were actually executed in this session. PBI-14-03's own run was against
branch `feat/pbi-14-03-multiagent-semantic-intelligence`; PBI-14-04's own run (see its own
subsection below) was against `feat/pbi-14-04-universal-semantic-routing`, branched from `main`
after PBI-14-03 was merged. No result is asserted without having run it.

## PBI-14-03 backend

| Command | Result |
|---|---|
| `python -m pytest tests/unit tests/conversational -q` | **796 passed**, 0 failed, 1 pre-existing unrelated warning (StarletteDeprecationWarning) |
| `python -m ruff check .` | **All checks passed** (full repository) |
| `python -m mypy src apps/api` | **7 pre-existing errors in `src/pipelines/knowledge_ingestion/index_schema.py`** (confirmed via `git status`/`git diff` — this file was never touched this session; `SimpleField`/`SearchFieldDataType` Enum-vs-str typing gap, unrelated to this PBI). Every touched file individually verified clean before this full-repo run. |

Targeted mypy/ruff runs during implementation (all clean, listed for traceability):
`src/llm/{models,azure_openai_provider,mock_provider}.py`,
`src/agents/shared/{semantic_models,semantic_interpreter,semantic_merge,confirmation}.py`,
`src/agents/{claims_agent,claims/workflow,claims/extraction}.py`,
`src/agents/{broker_agent,broker/workflow,broker/extraction}.py`,
`src/agents/{commercial_intake_agent,commercial/workflow,commercial/state}.py`,
`src/supervisor/{intent,orchestrator,models}.py`,
`src/domain/observability.py`,
`src/services/observability_store/{in_memory,cosmos}.py`,
`apps/api/src/api/routes/{chat,observability}.py`.

## PBI-14-03 frontend

| Command | Result |
|---|---|
| `npm run test -- --run` (apps/web) | **8 test files, 42 tests passed** |
| `npm run typecheck` (apps/web) | Clean (`tsc --noEmit`, no errors) |
| `npm run lint` (apps/web) | Clean (`eslint .`, no errors) |
| `npm run build` (apps/web) | Succeeded — `tsc --noEmit && vite build`, 219 modules transformed, no errors |

## PBI-14-03 new tests added

- `tests/unit/agents/shared/test_confirmation.py` (13 tests)
- `tests/unit/agents/shared/test_semantic_merge.py` (4 tests)
- `tests/unit/agents/shared/test_semantic_interpreter.py` (5 tests, incl. a schema-shape
  assertion that no chain-of-thought/reasoning field exists)
- `tests/unit/agents/test_claims_agent_semantic_regression.py` (1 end-to-end scenario test)
- `tests/unit/agents/test_broker_agent_semantic_regression.py` (1 end-to-end scenario test)
- `tests/unit/agents/test_commercial_intake_agent_semantic_regression.py` (1 end-to-end scenario
  test)
- `tests/unit/services/test_observability_store_in_memory.py` — 5 new cost-nullability tests
  appended to the existing file
- `tests/unit/supervisor/test_intent.py` — 4 new parametrized cases appended (incendio/fábrica
  hard case, English equivalent, `póliza`/`pago` keyword-gap cases)
- 2 pre-existing extraction-level tests removed (relocated coverage — see `decisions.md` item 5)

Net: 796 backend tests passing (up from 738 at the start of this PBI's implementation phase,
before that: 682 + 18 from PBI-12-04 per ADR-0011's own log — continuous growth, no regression).

## PBI-14-03 not run (and why)

- Real Azure OpenAI structured-output call — `AzureOpenAIProvider` is never exercised against
  real Azure by this test suite (documented, pre-existing limitation, same as every other
  Azure-dependent adapter in this repo).
- Cosmos DB — same documented limitation; `CosmosObservabilityRepository`'s fix is
  code-reviewed and pattern-consistent with the test-verified in-memory equivalent, not
  runtime-verified (see `decisions.md` item 6).
- Azure deployment / `docker build` / `az containerapp update` / `az deployment group create` —
  explicitly out of scope per CLAUDE.md §7.1 (Azure DevOps CI/CD owns deployment) and the
  driving PBI's own "Do NOT deploy" instruction.

## PBI-14-04 backend

| Command | Result |
|---|---|
| `python -m pytest tests/unit tests/conversational -q` | **851 passed**, 0 failed, 1 pre-existing unrelated warning |
| `python -m ruff check .` | **All checks passed** (full repository) |
| `python -m mypy src apps/api` | Same **7 pre-existing errors** in `src/pipelines/knowledge_ingestion/index_schema.py`, still confirmed untouched this session — every touched file individually verified clean first. |

## PBI-14-04 frontend

No frontend source file was touched by this PBI (backend/routing-only change). Full suite run
anyway to confirm no incidental regression:

| Command | Result |
|---|---|
| `npm run test -- --run` (apps/web) | **9 test files, 50 tests passed** |
| `npm run typecheck` (apps/web) | Clean |
| `npm run lint` (apps/web) | Clean |
| `npm run build` (apps/web) | Succeeded — 219 modules transformed, no errors |

## PBI-14-04 new tests added

- `tests/unit/supervisor/test_semantic_routing.py` (10 tests) — every confidence band,
  explicit-clarification flag, both degraded-call detection paths (LLM exception, malformed
  JSON).
- `tests/unit/supervisor/test_semantic_routing_domain_paraphrases.py` (31 parametrized tests) —
  sections 11-14's exact Claims/Broker/Commercial/unknown phrases, plus the two current-goal
  pair cases and the exact production regression sentence.
- `tests/unit/supervisor/test_pbi_14_04_production_regression.py` (3 tests) — the full
  Supervisor + real ClaimsAgent + real Tools pipeline: production regression sentence reaches
  ClaimsAgent, exactly one structured semantic call per turn (call-counting
  `MockLLMProvider` subclass), ReAct/Tool-Calling still runs, and a 3-turn intent-switch
  (Claims -> Broker -> Commercial) with isolated per-domain state.
- `tests/unit/agents/test_fallback_agent.py` (6 tests) — plain vs. clarification messages, all
  three domain-pair templates plus the generic fallback, and a check that
  `turn_interpretation.routing_reason` never leaks into the user-facing response.
- `tests/unit/agents/shared/test_turn_interpretation.py` (5 tests) — `to_domain_interpretation`
  field mapping/adaptation, `None`-turn safe degradation, and a chain-of-thought schema-shape
  assertion.
- `tests/unit/supervisor/test_orchestrator.py` — updated (not counted as new) to construct
  `SupervisorOrchestrator` with the two new `prompt_manager`/`llm_provider` dependencies; every
  existing assertion kept its original meaning (a bare `MockLLMProvider()` with no scripted
  structured response degrades the semantic call, exercising the same
  `RuleBasedIntentResolver` keyword path these tests already verified before this PBI).

Net: 851 backend tests passing (up from 796 at the start of this PBI's implementation phase),
zero regressions, zero pre-existing tests modified for behavior reasons (only the orchestrator
constructor-argument updates above, which are call-site adaptations, not behavior changes).

## PBI-14-04 not run (and why)

- Real Azure OpenAI classification of the section 11-14 paraphrase test cases — this sandbox has
  `LLM_PROVIDER=mock` configured locally with no Azure OpenAI credentials available (same
  documented, pre-existing limitation noted under PBI-14-03 above). The domain-paraphrase tests
  verify the deterministic routing/reuse LOGIC given a classification, not real-model
  classification accuracy for these exact phrasings — see `decisions.md` item 4 and the
  "live-like local validation" note in the final PBI-14-04 report.
- Cosmos DB, Azure deployment, `docker build` — same reasons as PBI-14-03 above; nothing new in
  this PBI changed that boundary.

## PBI-14-05 — `azure-pipelines.yml` delivery consistency

This sandbox has no Azure DevOps project connection and cannot execute a real pipeline run
(see `decisions.md` item 3). Validation is therefore YAML-syntax verification plus a
line-cited structural walkthrough proving each of the 6 required-validation items, run against
the actual committed file content.

### YAML syntax

```
$ python -c "import yaml; yaml.safe_load(open('azure-pipelines.yml', encoding='utf-8'))"
YAML parsed OK — 11 stages (unchanged count from before this PBI):
BackendQuality, FrontendQuality, SecurityScan, InfrastructureValidation, InfrastructureDeploy,
ContainerBuildValidation, ContainerBuildAndPush, DeployDev, SmokeTests, DeploymentSummary,
ArtifactPublication
```

### 1. On a main deploy run, Web build executes even when apps/web did not change

`ContainerBuildAndPush` (`azure-pipelines.yml:753`, `condition: eq(variables.isDeployRun, true)`
— main only) builds the Web image at line 840
(`echo "=== Building Web image (always; context apps/web, ...)"` immediately followed by
`docker build ... apps/web`) with NO `if` guard around it — the previous
`if [ "$(detectWebChange.webChanged)" = "true" ]` conditional was removed. The
`detectWebChange` step (lines ~793-810) still computes the diff, but its output
(`webChangedInfoOnly`) is consumed ONLY by `DeploymentSummary` for reporting, never by any
build/push/deploy step.

### 2. On a main deploy run, Web deploy executes even when apps/web did not change

`DeployDev` (`azure-pipelines.yml:869`, same `isDeployRun` condition) runs
`az containerapp update --name "$WEB_APP_NAME" ...` at line ~900-901 with NO `if` guard —
the previous `if [ "$(webChanged)" = "true" ]` conditional, and the stage's own `webChanged`
variable declaration that read it from `ContainerBuildAndPush`'s output, were both removed.

### 3. API and Web use the same BuildId + commit-SHA image tag

`imageTag: 'dev-$(Build.BuildId)-$(Build.SourceVersion)'` (`azure-pipelines.yml:186`) is a
single pipeline-level variable, evaluated once per run. Both the API build
(`-t "$ACR_LOGIN_SERVER/$(apiImageName):$(imageTag)"`) and the Web build
(`-t "$ACR_LOGIN_SERVER/$(webImageName):$(imageTag)"`) reference this exact same variable
inside the SAME `AzureCLI@2` inline script in `ContainerBuildAndPush` — they cannot diverge
within one run. `DeployDev` and the new Smoke Tests step both re-derive
`$(apiImageName):$(imageTag)` / `$(webImageName):$(imageTag)` the same way and compare them
against each Container App's actual deployed `properties.template.containers[0].image` —
Smoke Tests 1/5 and 2/5 (`azure-pipelines.yml:953`, `:973`) fail the pipeline (`exit 1`) on any
mismatch.

### 4. PR validation still does not deploy anything

`ContainerBuildValidation` (`azure-pipelines.yml:665`,
`condition: ne(variables.isDeployRun, true)`) contains no `AzureCLI@2` task, no
`azureSubscription`, and no `docker push` — only two plain `docker build ... ` steps whose
images are discarded when the job ends (confirmed unchanged: zero diff hunks fall inside this
stage's line range). `isDeployRun` (`azure-pipelines.yml:187`) is only `true` when
`Build.SourceBranch == refs/heads/main`; a PR's source branch is never `refs/heads/main`, so
`ContainerBuildAndPush`, `InfrastructureDeploy`, `DeployDev`, `SmokeTests`, and
`DeploymentSummary` (all `condition: eq(variables.isDeployRun, true)`) never run on a PR run,
exactly as before this PBI.

### 5. No Azure resources are recreated

`InfrastructureDeploy` (`azure-pipelines.yml:593`) — the ONLY stage that runs
`az deployment group create`/`validate` — has zero diff hunks (confirmed: every hunk in this
PBI's diff starts at old-line 736 or later, and `InfrastructureDeploy` ends at line 650 in the
pre-change file). `DeployDev`'s only Azure-mutating call is
`az containerapp update --image ...` (image reference only — `azure-pipelines.yml:882`'s own
comment: "image only, no infra recreation"), unchanged in kind from before this PBI, now simply
called unconditionally for both apps instead of conditionally for Web.

### 6. Existing quality/security/build gates remain intact

`BackendQuality` (line 196), `FrontendQuality` (line 296), `SecurityScan` (line 376),
`InfrastructureValidation` (line 535), and `ContainerBuildValidation` (line 665) all have zero
diff hunks — confirmed via `git diff -- azure-pipelines.yml | grep '^@@'`, every hunk's starting
line falls at 736 or later, strictly after all five of these stages end in the pre-change file.
`ContainerBuildAndPush`/`DeployDev`/`SmokeTests`/`DeploymentSummary` still `dependsOn` the same
upstream stages as before (`BackendQuality`/`FrontendQuality`/`SecurityScan` for
`ContainerBuildAndPush`; `ContainerBuildAndPush`/`InfrastructureValidation` for `DeployDev`) —
none of those `dependsOn` lists were touched.

### Not run (and why)

- A real Azure DevOps pipeline execution — no Azure DevOps project/service connection is
  reachable from this sandbox (see `decisions.md` item 3). The structural evidence above is a
  faithful, line-cited substitute, not a substitute for an actual run confirming DEV's Web
  Container App ends up on the correct image — that confirmation can only come from the next
  real `main` pipeline run once this change is merged.
- `apps/web/vite.config.ts` — deliberately not modified, and not re-tested, per the explicit
  instruction not to touch it absent contradicting evidence (none was found — see this file's
  PBI-14-05 root-cause section in `README.md`).

## PBI-14-06 (deployment verification + build/version visibility)

This session had real, authenticated `az` CLI access (subscription Owner on the real DEV
subscription/tenant) — unlike PBI-14-04/14-05, which both disclosed no Azure credentials were
available. All commands below were actually executed.

### Section 1 — deployment-state evidence (gathered before any implementation)

| Check | Command | Result |
|---|---|---|
| Current `origin/main` HEAD | `git fetch origin && git log --oneline -1 origin/main` | `ad67be6` (PR #51 merge, PBI-14-05) |
| DEV API Container App | `az containerapp show --name ca-tmxap-dev-api ...` | Active revision `ca-tmxap-dev-api--0000035`, 100% traffic, image `...tmx-api:dev-46-ad67be64822245a4d305ef3448544fcac465b9ae` |
| DEV Web Container App | `az containerapp show --name ca-tmxap-dev-web ...` | Active revision `ca-tmxap-dev-web--0000017`, 100% traffic, image `...tmx-web:dev-46-ad67be64822245a4d305ef3448544fcac465b9ae` |
| Image tag == `origin/main` HEAD | exact string comparison | Both images' embedded commit SHA exactly matches `origin/main`'s full HEAD SHA — DEV is current, not stale |
| PBI-14-03 in deployed commit | `git merge-base --is-ancestor 0a71020 ad67be6...` | **Yes — is an ancestor** |
| PBI-14-04 in deployed commit | `git merge-base --is-ancestor 767bc03 ad67be6...` | **Yes — is an ancestor** |
| Deployed API's LLM provider | `az containerapp show ... --query env vars` | `LLM_PROVIDER=azure_openai`, endpoint `https://aoai-tmxap-dev-l3fgxt.openai.azure.com/`, deployment `chat`, model `gpt-5-mini` — real Azure OpenAI, not mock |
| `GET /health` reachable | `curl https://.../health` | `{"status":"ok"}` |

**Conclusion: both PBI-14-03 and PBI-14-04 (universal semantic routing) ARE deployed to DEV** —
per the driving task's own branching logic, this means section 8 requires a live diagnostic, not
a "stop and report drift" outcome.

### Backend

| Command | Result |
|---|---|
| `python -m ruff check apps/api/src/config/settings.py apps/api/src/api/routes/version.py` | All checks passed |
| `python -m mypy apps/api/src/config/settings.py apps/api/src/api/routes/version.py` | Success: no issues found in 2 source files |
| `python -m pytest tests/unit/api -q` (run from repo root) | **89 passed**, 0 failed (the same command run from `apps/api/src` shows 26 unrelated pre-existing failures — `LocalKnowledgeProvider`'s relative path resolves against cwd; a cwd artifact, not a regression, reproduced identically on the unmodified `origin/main` baseline) |
| `python -m pytest tests/unit/api/test_version.py -v` | **3 passed** — includes 2 new tests: `test_version_includes_build_traceability_fields`, `test_version_build_traceability_fields_are_sourced_from_settings_not_hardcoded` |

### Frontend

| Command | Result |
|---|---|
| `npx tsc --noEmit` (apps/web) | Clean, no errors |
| `npm run lint` (apps/web) | Clean (`eslint .`, no errors) |
| `npm run test -- --run` (apps/web) | **9 test files, 50 tests passed** |

### Pipeline

| Command | Result |
|---|---|
| `python -c "import yaml; yaml.safe_load(open('azure-pipelines.yml'))"` | Parsed OK, **11 stages** — identical count to the pre-change file |
| `git diff -U0 azure-pipelines.yml \| grep '^@@'` | Every hunk falls within `variables` (~line 187), `ContainerBuildAndPush` (~817-855), `SmokeTests` (~929-1109), `DeploymentSummary` (~1235) — `ContainerBuildValidation`, `BackendQuality`, `FrontendQuality`, `SecurityScan`, `InfrastructureValidation`, `InfrastructureDeploy`, `ArtifactPublication` all have zero diff hunks |

### Real end-to-end Docker verification (this sandbox has a working Docker daemon)

Actually built both images with pipeline-shaped build-args and ran the containers — not just a
structural review:

| Step | Command | Result |
|---|---|---|
| Build API image | `docker build --file apps/api/Dockerfile --build-arg APP_VERSION=14.6.0 --build-arg BUILD_NUMBER=999 --build-arg COMMIT_SHA=testsha1234 -t tmx-api:pbi1406test .` | Succeeded |
| Verify Settings picked up build-args | `docker run --rm tmx-api:pbi1406test python -c "from config.settings import Settings; ..."` | `app_version=14.6.0 build_number=999 commit_sha=testsha1234` |
| Boot container, call real endpoint | `docker run -d -p 18000:8000 ...` then `curl http://localhost:18000/version` | `{"name":"tmx-enterprise-ai-reference-platform","version":"0.1.0","environment":"local","app_version":"14.6.0","build_number":"999","commit_sha":"testsha1234","component":"api"}` |
| Build Web image | `docker build --build-arg VITE_APP_VERSION=14.6.0 --build-arg VITE_BUILD_NUMBER=999 --build-arg VITE_COMMIT_SHA=testsha1234 -t tmx-web:pbi1406test apps/web` | Succeeded |
| Boot container, verify commit SHA in served bundle | `curl http://localhost:18001/` → extract `/assets/main-*.js` → `curl .../assets/main-*.js \| grep testsha1234` | Commit SHA literal found in the served JS bundle — **this is the exact mechanism the new Smoke Test 4/7 uses, now proven working, not just theoretically correct** |

Both test images and containers were removed after verification (`docker rmi`/`docker rm -f`) —
nothing pushed to any registry, no Azure resource touched.

### Section 8 — live semantic-routing diagnostic (real Azure OpenAI, real repo code)

Ran `src.supervisor.semantic_routing.resolve_turn` (unmodified) against the real DEV Azure
OpenAI resource (`https://aoai-tmxap-dev-l3fgxt.openai.azure.com/`, deployment `chat`, model
`gpt-5-mini`) using `AzureOpenAIProvider`'s own `DefaultAzureCredential` path, for the exact
(unaccented) regression sentence: *"quiero reportar un percance derivado de la fuerte lluvia que
cayó hoy un camión me pego por atras"*.

| Step | Result |
|---|---|
| Prompt render (`supervisor.turn_interpretation`) | **Succeeded** — `[prompt=supervisor.turn_interpretation@1.0.0]` |
| Request construction (model/deployment/temperature handling) | **Correct** — reasoning-family capability gap for `gpt-5-mini` handled as designed (temperature omitted, WARNING logged) |
| Network call to real Azure OpenAI endpoint | **Reached the real endpoint** |
| Call result | `401 PermissionDenied`: *"The principal `jose_marin@tokiomarine.com.mx` lacks the required data action `Microsoft.CognitiveServices/accounts/OpenAI/deployments/chat/completions/action`"* |
| `resolve_turn` graceful degradation | Worked exactly as designed: `routing_source=deterministic_fallback`, `routing_reason=semantic_service_unavailable`, fell back to `RuleBasedIntentResolver`, which also resolved this sentence to `UNKNOWN` (no keyword match) |

This is a genuine, disclosed limitation, not a bug: my own Azure CLI identity (subscription
Owner) was never expected to carry Azure OpenAI **data-plane** access — the built-in Owner role's
`DataActions` is empty by Azure's own design; only the deployed app's managed identity
(`id-tmxap-dev`) was explicitly granted "Cognitive Services OpenAI User"
(`az role assignment list --assignee e4fb11f4-cf47-4926-a1e3-a8dfaf04d77c --all`, confirmed).
Completing this diagnostic as the deployed application's own identity requires either a real
delegated Entra user Bearer token (blocked: `az account get-access-token --resource
api://67d95215-... ` fails with `AADSTS65001 consent_required`, interactive-only) or granting
this session's identity the same data-plane RBAC role (a real Azure IAM change, not made without
explicit authorization — outside "implement code for the current PBI"). See `decisions.md` item 5
for the full writeup.

### Not run (and why)

- A real Azure DevOps pipeline execution — still not reachable from this sandbox even with real
  `az` CLI access (the pipeline itself runs on Azure DevOps-hosted agents, a separate system from
  the subscription's own control/data planes this session can reach directly).
- The real semantic-routing call as the deployed application's own managed identity, or via a
  real delegated user token through `POST /chat` — both blocked by independently-confirmed,
  disclosed auth boundaries (see Section 8 above), neither of which this PBI is authorized to
  work around (would require either an IAM grant or touching authentication, both out of scope).

## PBI-14-07 (structured routing telemetry fix)

All commands below were actually executed in this session.

### Root-cause verification (section 1's mandatory pre-implementation gate)

| Check | Result |
|---|---|
| Read `apps/api/src/observability/logging.py` | `JsonFormatter.format()` builds `payload` from 5 fixed keys only; never reads `record.__dict__` beyond `correlation_id` |
| Live confirmation (Log Analytics, same session) | Real `supervisor_turn_latency` log lines from the deployed API contained only `timestamp`/`level`/`logger`/`message`/`correlationId` — the `extra=` fields the code sets were absent, matching the code-read diagnosis exactly |
| Conclusion | Root cause confirmed as diagnosed — proceeded to implementation, no scope deviation |

### Manual formatter verification (real code, not a mock)

```
$ python -c "... logger.info('Semantic routing decision', extra={...25 fields incl. authorization=...})"
{"timestamp": "...", ..., "authorization" NOT present, all 15 allowlisted fields present}
```
Confirmed: allowlisted fields survive, `authorization` and one deliberately-unapproved key are
both silently absent, `null` and list values both handled cleanly. See `decisions.md` for the
full field-by-field design rationale.

### Backend tests

| Command | Result |
|---|---|
| `pytest tests/unit/api/test_json_formatter.py -v` | **10 passed** (new file) |
| `pytest tests/unit/api/test_semantic_routing_log_events.py -v` | **5 passed** (new file) |
| `pytest tests/unit/supervisor/test_semantic_routing.py -v` | **13 passed** (10 pre-existing + 3 new `_classify_semantic_error` unit tests; 5 pre-existing tests gained additive `semantic_call_succeeded`/`semantic_error_category` assertions, none had their prior assertions changed) |
| `pytest tests/unit/supervisor/test_pbi_14_04_production_regression.py -v` | **3 passed, completely unmodified** — per explicit instruction |
| `pytest tests/unit tests/conversational -q` (full suite, repo root) | **871 passed**, 0 failed, 1 pre-existing unrelated warning (StarletteDeprecationWarning) |
| `ruff check` (7 touched files) | **All checks passed** (6 mechanical issues — unused `noqa: S106` since that rule isn't enabled in this repo, import sort order, one unused import — auto-fixed via `ruff check --fix`, then re-verified clean) |
| `mypy` (4 non-test touched files: `semantic_routing.py`, `orchestrator.py`, `logging.py`, `chat.py`) | **Success: no issues found in 4 source files** |

### Frontend impact

**None.** No frontend file was read or modified for this PBI — the driving task's own section 18
asked to confirm this rather than touch the frontend "merely to create work." `npm run
test`/`lint`/`typecheck` were not re-run since nothing under `apps/web` changed in this PBI (they
were already run, clean, under PBI-14-06 earlier in this session).

### Application Insights compatibility (section 16)

No new telemetry backend was introduced — the fix operates entirely within the existing stdout
JSON logging path (`configure_logging()` → `logging.StreamHandler(sys.stdout)` →
`JsonFormatter`). Per PBI-14-06's own investigation (still valid, re-confirmed, not
re-litigated): Application Insights receives **zero** telemetry today because no code anywhere
in the repo calls `configure_azure_monitor()` or initializes any Azure Monitor/OpenTelemetry
exporter — this JSON still lands only in Container App stdout, forwarded to Log Analytics'
`ContainerAppConsoleLogs_CL` table (confirmed live, real data, during PBI-14-06). It is **not**
true that Application Insights automatically maps this JSON's fields into queryable
`customDimensions` — that requires an actual exporter, which does not exist in this codebase.
Until that gap is closed (a separate, larger PBI — instrumenting `configure_azure_monitor()` is
an infrastructure/dependency change, correctly out of this PBI's own scope), the query path is:
`ContainerAppConsoleLogs_CL | where Log_s has 'semantic_routing_decision' | extend parsed =
parse_json(Log_s)` (KQL, Log Analytics) — the exact table and pattern already used to confirm
this defect live.

### Real, locally-generated formatter output (section 17 — not hand-written)

Captured verbatim from `pytest -s` output of the new integration tests (real
`SupervisorOrchestrator` → real `resolve_turn` → real `chat.py` → real `JsonFormatter`):

Successful semantic routing:
```json
{"timestamp": "2026-08-14T13:49:50-0600", "level": "INFO", "logger": "api.routes.chat", "message": "Semantic routing decision", "correlationId": "test-correlation-id", "event": "semantic_routing_decision", "durationMs": 7.2, "conversationId": "9e85d538-14ae-4b13-ba89-4f898b389ee4", "semanticCallAttempted": true, "intentConfidence": 0.91, "messageId": "f5ac2481-e139-451d-a2b0-b63eff26d51f", "semanticErrorCategory": null, "routingSource": "semantic", "detectedIntent": "CLAIMS", "selectedAgent": "ClaimsAgent", "alternativeIntents": null, "semanticCallSucceeded": true, "routingReason": "semantic_match:claims", "requiresClarification": false, "runId": "f7696b50-4083-486e-8d66-362d296b8652"}
```

Semantic service failure (provider outage, deterministic fallback recovered via keyword match):
```json
{"timestamp": "2026-08-14T13:49:56-0600", "level": "INFO", "logger": "api.routes.chat", "message": "Semantic routing fallback", "correlationId": "test-correlation-id", "alternativeIntents": null, "selectedAgent": "ClaimsAgent", "intentConfidence": 0.0, "durationMs": 6.4, "semanticCallSucceeded": false, "messageId": "f64eb1da-2371-4a4c-b694-230b8e5fc491", "detectedIntent": "CLAIMS", "event": "semantic_routing_fallback", "conversationId": "71daed41-800e-4b33-9316-7e6cdeb58cec", "runId": "629bc84e-b505-41c4-a55e-ab33887ae63b", "routingSource": "deterministic_fallback", "semanticCallAttempted": true, "routingReason": "semantic_service_unavailable", "semanticErrorCategory": "provider_error", "requiresClarification": false}
```

### Not run (and why)

- A real deployment / real DEV log query for THIS specific fix — per explicit instruction, this
  PBI does not deploy. Section 20/25's exact post-deployment validation procedure is documented
  in `decisions.md`/the final report rather than executed here.
- `apps/web` tests — nothing under `apps/web` changed in this PBI (see "Frontend impact" above).

## PBI-14-08 (DeployDev / InfrastructureDeploy race condition)

Unlike prior PBIs in this sprint, this diagnosis was backed by a REAL Azure DevOps pipeline
execution — the `azure-devops` `az` CLI extension successfully queried the actual build #50
timeline and step logs (previously listed as "Not run (and why)" in earlier PBIs of this sprint;
this access was exercised for the first time here).

| Check | Command | Result |
|---|---|---|
| Real build timeline (stage start/finish) | `az devops invoke --area build --resource Timeline --route-parameters buildId=50 ...` | Confirmed: stage 5 (DeployDev) finished `23:14:37Z`, stage 4b (InfrastructureDeploy) finished `23:17:50Z` — 4b after 5 |
| Cross-check against a known-good run | same query, `buildId=46` | Confirmed opposite ordering (4b finished `16:59:14Z`, before 5's `17:00:21Z`) — proves the race is real and non-deterministic, not a new deterministic regression |
| DeployDev's own step log | `az devops invoke --area build --resource Logs --route-parameters buildId=50 logId=94 ...` | Confirmed both `az containerapp update` calls succeeded with the correct `dev-50-321ce9fe...` images at the time they ran |
| Live Azure state (API) | `az containerapp show --name ca-tmxap-dev-api ...` | `pending-first-build`, revision `--0000037`, created `23:17:22Z` (inside 4b's window) |
| Live Azure state (Web) | `az containerapp show --name ca-tmxap-dev-web ...` | `pending-first-build`, revision `--0000019`, created `23:16:02Z` |
| ACR contents | `az acr repository show-tags --name acrtmxapdevl3fgxt --repository tmx-api/tmx-web` | Both `dev-50-321ce9fe...` tags present — confirms build/push was never at fault |
| `ops/bicep/parameters/dev.bicepparam` | `grep pending-first-build ops/bicep/parameters/*.bicepparam` | `apiImageTag`/`webImageTag = 'pending-first-build'` confirmed hardcoded |
| `ops/bicep/modules/container-app.bicep` | manual read | `resource containerApp ... = {...}` (full, non-`existing` declaration), `image: '${...}/${imageName}:${imageTag}'` bound directly to the hardcoded parameter |

### After the fix

| Check | Command | Result |
|---|---|---|
| YAML parses | `python -c "import yaml; yaml.safe_load(open('azure-pipelines.yml'))"` | Parsed OK, **11 stages** — identical count to the pre-change file |
| `DeployDev.dependsOn` includes `InfrastructureDeploy` | same script, inspect `dependsOn` | `['ContainerBuildAndPush', 'InfrastructureValidation', 'InfrastructureDeploy']` |
| `DeployDev.condition` never checks `InfrastructureDeploy`'s result | same script, inspect `condition` | Explicit `in(dependencies.ContainerBuildAndPush.result, 'Succeeded')` / `in(dependencies.InfrastructureValidation.result, 'Succeeded')` checks only — no reference to `InfrastructureDeploy` |
| `git diff --stat` | `git diff --stat` | `azure-pipelines.yml` — single hunk, 29 insertions/1 deletion, strictly inside `DeployDev`'s own block |
| Nothing else touched | `git status --short ops/bicep/ src/ apps/` | Empty — zero Bicep or application code changes |

### Not run (and why)

- A real Azure DevOps pipeline execution of THIS fix — per explicit instruction, this PBI does
  not deploy; the fix's real-world effect can only be confirmed on the next actual `main` run.

## PBI-14-11 (DEV deployment stabilization)

### Phase 1-3 forensics (all against real, live Azure/Azure DevOps — no assumptions)

| Check | Command | Result |
|---|---|---|
| `origin/main` HEAD | `git fetch origin main && git rev-parse origin/main` | `0d7b3044dfe985edeeaab48357606a633657f4d5` |
| Latest main pipeline run | `az pipelines build list --branch refs/heads/main --top 1` | Build #57, `sourceVersion=0d7b304...`, result **failed** |
| Stage timeline, build #57 | `az devops invoke --area build --resource Timeline --route-parameters buildId=57` | `InfrastructureDeploy` succeeded 02:11-02:13Z, **before** `DeployDev` started 02:13-02:14Z (PBI-14-08 ordering held); `SmokeTests` failed 02:15Z |
| Per-test smoke results, builds #52/#55/#57 | same Timeline query, `records[?contains(name,'Smoke test')]` | Identical pattern all three runs: tests 1-5 (API/Web tag, API/Web build-commit identity, health) **pass**; test 6/7 (`POST /chat`) **fails** |
| Smoke test 6/7 raw log | `curl .../_apis/build/builds/57/logs/120` | `Bash exited with code '22'` (curl `-f` HTTP-error exit) |
| Live API/Web Container App state | `az containerapp show --name ca-tmxap-dev-{api,web} ...` | Both running `dev-57-0d7b304...`, `provisioningState: Succeeded` |
| Live Web root fetch | `curl -s -o ... -w "HTTP_STATUS:%{http_code}" https://ca-tmxap-dev-web.../` | **HTTP 200**, correct `index.html`, `grep -i blocked` → no match |
| Live API `/version` | `curl https://ca-tmxap-dev-api.../version` | `build_number=20260815.5, commit_sha=0d7b3044...` — matches `origin/main` HEAD exactly |
| Live `/chat` reproduction | `curl -X POST https://ca-tmxap-dev-api.../chat -d '{...}'` | **HTTP 401** `"A valid Bearer token is required"` — confirms test 6/7's real cause, unrelated to Web |
| Web revision/traffic state | `az containerapp revision list --name ca-tmxap-dev-web ...` | 1 revision, `active=True`, `trafficWeight=100`, `activeRevisionsMode: Single` |
| 7-day Web log search | Log Analytics KQL: `ContainerAppConsoleLogs_CL \| where ContainerAppName_s == "ca-tmxap-dev-web" \| where Log_s has "Blocked request" or Log_s has "not allowed"` | **0 rows** |
| Log window coverage | KQL: `... \| summarize count(), min(TimeGenerated), max(TimeGenerated)` | 166 rows, `2026-08-08T00:35:12Z` → `2026-08-15T02:15:33Z` (full 7-day retention, not a false-negative from a short window) |
| ACR tag-immutability support | `az acr show --name acrtmxapdevl3fgxt --query policies` | `"Policies are only supported for managed registries in Premium SKU"` — confirms Basic/Standard SKU has no tag-immutability guarantee |
| Digest consistency (pre-fix) | `az acr repository show --image tmx-web:dev-57-... --query digest` vs. `az containerapp show --query properties.template.containers[0].image` | ACR digest `sha256:ab663f5...` matched the live app's referenced tag at time of check — no drift found, but tag (not digest) was the reference in use |

### Phase 6 implementation validation

| Check | Command | Result |
|---|---|---|
| YAML parses | `python -c "import yaml; yaml.safe_load(open('azure-pipelines.yml'))"` | Parsed OK, **11 stages**, same set as before |
| Bicep builds (main) | `az bicep build --file ops/bicep/main.bicep --stdout` | exit 0, no errors/warnings |
| Bicep builds (module) | `az bicep build --file ops/bicep/modules/container-app.bicep --stdout` | exit 0, no errors/warnings |
| Bicep params build | `az bicep build-params --file ops/bicep/parameters/dev.bicepparam --stdout` | exit 0, no errors/warnings |
| **Live, non-mutating** ARM validation — tag-preservation path | `az deployment group validate -g rg-tmx-agent-platform-dev --template-file ops/bicep/main.bicep --parameters ops/bicep/parameters/dev.bicepparam --parameters apiImageTag=<current live tag> webImageTag=<current live tag>` | `provisioningState: Succeeded` against the real DEV resource group |
| **Live, non-mutating** ARM validation — digest-pinning path | same command with `apiImageDigest=<real ACR digest> webImageDigest=<real ACR digest>` instead of tags | `provisioningState: Succeeded` against the real DEV resource group |
| Diff scope | `git status --short` / `git diff --stat` | Exactly 3 files: `azure-pipelines.yml` (+117/-19), `ops/bicep/main.bicep` (+8), `ops/bicep/modules/container-app.bicep` (+6/-1). No `vite.config.ts`, no `src/`, no `apps/api/src/api/dependencies.py`, no `dev.bicepparam` |
| Existing test suite relevance | `grep -rl "bicep\|azure-pipelines" tests/` | No matches — no existing pytest/vitest suite targets these infra files (consistent with PBI-14-05/14-08, also infra-only changes validated the same way); not applicable rather than skipped |

### Not run (and why)

- A real Azure DevOps pipeline execution of this fix (`az deployment group create`, an actual
  `main` push) — per the task's explicit "STOP BEFORE COMMIT... DO NOT DEPLOY" instruction, this
  PBI does not commit, push, or deploy. `az deployment group validate` (non-mutating, read-only)
  was run against the real resource group instead, as the closest available proof short of an
  actual apply.
- A fix for the `/chat` 401 smoke-test failure — out of scope for this PBI (see `decisions.md`);
  reported to the user, not fixed here.

## PBI-14-12 (Structured Outputs failure — three chained defects)

This entry documents evidence already gathered during the implementation session that produced
commit `4a2421e`, reconstructed here because no `validation.md` entry existed for it (see
`decisions.md`). No test/lint/type-check command was re-executed in this documentation-only
session; the table below cites `4a2421e`'s own commit message and diff, not a fresh run.

### Diagnosis and live DEV reproduction (from commit `4a2421e`'s message)

| Check | Result |
|---|---|
| Exact acceptance sentence, real DEV Azure OpenAI, after all three fixes | `semanticCallSucceeded=true`, `semanticErrorCategory=null`, `detectedIntent=CLAIMS`, `selectedAgent=ClaimsAgent`, `routingSource=semantic` |
| `routingReason` consistency | Not `semantic_service_unavailable` — per PBI-14-07's `RoutingDecision` contract (this file's PBI-14-07 section), that reason string only ever accompanies `routing_source=deterministic_fallback`, never `routing_source=semantic` |

### Code changes (`4a2421e` vs. its parent `9447b28`; this session's `git diff --numstat`)

| File | Insertions | Deletions |
|---|---|---|
| `src/agents/shared/semantic_models.py` | 54 | 11 |
| `src/agents/shared/semantic_interpreter.py` | 25 | 1 |
| `src/llm/azure_openai_provider.py` | 41 | 0 |
| `tests/unit/agents/shared/test_semantic_interpreter.py` | 78 | 1 |
| `tests/unit/agents/shared/test_turn_interpretation.py` | 207 | 44 |
| `tests/unit/llm/test_azure_openai_provider.py` | 65 | 0 |

### PR/branch forensics (commands actually executed in this documentation-only session)

| Check | Command | Result |
|---|---|---|
| `49c661b` (PR #57) ancestry vs. `main` | `git merge-base --is-ancestor 49c661b main` | Not an ancestor — never merged into `main` |
| `49c661b` (PR #57) ancestry vs. `4a2421e` | `git merge-base --is-ancestor 49c661b 4a2421e` | Not an ancestor — `4a2421e` was not built on top of it |
| `49c661b` PR ref state | `git ls-remote origin "refs/pull/57/*"` | Only `refs/pull/57/head`, no `refs/pull/57/merge` — closed without merging |
| `4a2421e` (PR #58) PR ref state | `git ls-remote origin "refs/pull/58/*"` | Both `refs/pull/58/head` and a live `refs/pull/58/merge` — open, currently mergeable against `main` |
| Shared parent | `git merge-base 49c661b 4a2421e` and `git merge-base 49c661b main` | Both resolve to `9447b28` — true siblings, both branched directly from the same `main` commit |
| `49c661b`'s full diff scope | `git diff 49c661b^ 49c661b --stat` | Exactly 2 files: `src/agents/shared/semantic_models.py`, `tests/unit/agents/shared/test_turn_interpretation.py` |
| File-level overlap, `semantic_models.py` | `git diff 49c661b 4a2421e -- src/agents/shared/semantic_models.py` | Empty — byte-identical between the two commits |
| File-level overlap, `test_turn_interpretation.py` | `git diff 49c661b 4a2421e -- tests/unit/agents/shared/test_turn_interpretation.py` | Empty — byte-identical between the two commits |
| Conclusion | — | `49c661b`'s entire diff is a strict, content-identical subset of `4a2421e`'s diff — fully superseded, nothing unique |
| `docs/sprint_14/` touched by either branch before this session | `git diff main <branch> -- docs/sprint_14/`, run for both `fix/pbi-14-12b-structured-outputs-schema-fix` and `fix/pbi-14-13-dev-diagnostic-loop` | Empty both times — confirms the documentation gap this entry closes |

### Not run (and why)

- `pytest`/`ruff`/`mypy` for the six changed files — not re-executed in this documentation-only
  session; per the user's explicit instruction, this session updates only
  `docs/sprint_14/README.md`, `decisions.md`, `validation.md` and touches no code, tests,
  prompts, pipeline, Bicep, auth, frontend, or routing logic. The six files' own test additions
  (`+470/-57` across the six files combined, per `git diff --stat`) are the evidence tests were
  added alongside the fix in the original implementation session; re-running the full suite is a
  natural pre-merge step for PR #58, not part of this documentation task.
- A fresh live DEV call for this documentation update — the live DEV evidence quoted above is
  `4a2421e`'s own previously-recorded result, not reproduced again here.
- Merging PR #58 or deploying anything — explicitly out of scope for this documentation-only
  update; PR #58 remains open, unmerged, as of this writing.

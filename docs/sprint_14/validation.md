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


# Sprint 04 Validation

Record only commands actually executed and their real results.

## 2026-08-08 — PBI-04-01: Azure DevOps CI/CD Pipeline for the DEV Environment

### Pre-work: read required files, confirm current live state

| Check | Result |
|---|---|
| Read `CLAUDE.md`, `docs/sprint_03/*`, `docs/Architecture/*`, `ops/bicep/*`, existing `azure-pipelines.yml` | Confirmed a working Sprint-0 CI pipeline already exists (5 stages + a disabled, documented `Deploy_Dev` stage); found two real, pre-existing defects (see `decisions.md`) |
| `az resource list --resource-group rg-tmx-agent-platform-dev` | All 12 resources from PBI-03-05/06 still present, `Succeeded` |
| `az containerapp show --name ca-tmxap-dev-api ...` | `latestRevisionName: ca-tmxap-dev-api--v5`, FQDN `ca-tmxap-dev-api.bluemushroom-e2f74836.eastus2.azurecontainerapps.io` |
| `ls ops/bicep/modules/*.bicep` | 14 module files — cross-checked against the pipeline's `bicepModuleFiles` list, which was missing 5 of them |

### Bicep RBAC additions — static validation only (not deployed to Azure this PBI)

| Command | Result |
|---|---|
| `az role definition list --name "AcrPush"` | Confirmed live role GUID `8311e382-0749-4cb8-b61a-304f252e45ec` — used in `container-registry.bicep`, not guessed |
| `az role definition list --name "Container Apps Contributor"` | Confirmed live role GUID `358470bc-b998-42bd-ab17-a7e34c199c0f` — used in `container-app.bicep`, not guessed |
| `az bicep build --file ops/bicep/main.bicep` | exit 0, 0 warnings |
| `az bicep build --file ops/bicep/modules/container-registry.bicep` | exit 0, 0 warnings |
| `az bicep build --file ops/bicep/modules/container-app.bicep` | exit 0, 0 warnings |
| `az bicep build-params` — dev/staging/prod | All exit 0 |

**Not executed this PBI**: `az deployment group create` to actually apply the RBAC additions to the real DEV environment — deliberately deferred pending explicit user approval; see `decisions.md`.

### Pipeline YAML validation

| Command | Result |
|---|---|
| `python -c "import yaml; yaml.safe_load(open('azure-pipelines.yml'))"` | Valid YAML syntax. Parsed 8 top-level stages: `BackendQuality`, `FrontendQuality`, `InfrastructureValidation`, `ContainerBuildAndPush`, `DeployDev`, `SmokeTests`, `DeploymentSummary`, `ArtifactPublication` |
| `az extension list` / `az devops configure -l` | No `azure-devops` CLI extension installed; no Azure DevOps organization configured in this session (confirmed via failed prompt for extension install and no default org) — a true server-side/schema-level Azure Pipelines validation (`az pipelines run --validate-only`) could not be performed. Documented as a scope boundary in `decisions.md`, not silently skipped |
| Manual schema/logic review against the working Sprint-0 baseline `azure-pipelines.yml` | Confirmed: task names (`UsePythonVersion@0`, `NodeTool@0`, `Cache@2`, `AzureCLI@2`, `PublishTestResults@2`, `PublishCodeCoverageResults@2`, `PublishPipelineArtifact@1`, `DownloadPipelineArtifact@2`) match Azure Pipelines' documented task catalog and versions already proven working in the preserved Stage 1-3 content; `${{ }}` template-expression vs. runtime `$[ ]`/`variables[]` expression syntax used consistently and correctly (verified against the one existing `${{ each }}` usage already in the file) |

### Local dry-run (real, read-only `az` CLI calls against the live DEV environment — exactly the queries embedded in the pipeline's inline scripts)

| Dry-run query (verbatim from the pipeline) | Result |
|---|---|
| `az acr list --resource-group rg-tmx-agent-platform-dev --query "[0].name"` | `acrtmxapdevl3fgxt` |
| `az acr list --resource-group rg-tmx-agent-platform-dev --query "[0].loginServer"` | `acrtmxapdevl3fgxt.azurecr.io` |
| `az containerapp list --resource-group rg-tmx-agent-platform-dev --query "[?ends_with(name, '-api')].name \| [0]"` | `ca-tmxap-dev-api` |
| `az containerapp list --resource-group rg-tmx-agent-platform-dev --query "[?ends_with(name, '-web')].name \| [0]"` | `ca-tmxap-dev-web` |
| `az containerapp show --resource-group rg-tmx-agent-platform-dev --name ca-tmxap-dev-api --query "properties.configuration.ingress.fqdn"` | `ca-tmxap-dev-api.bluemushroom-e2f74836.eastus2.azurecontainerapps.io` |
| `az containerapp show ... --query "properties.latestRevisionName"` (api, web) | `ca-tmxap-dev-api--v5`, `ca-tmxap-dev-web--phnq58i` |
| **Smoke test 1/2**: `curl -sf --max-time 30 https://<api-fqdn>/health` | `200 {"status":"ok"}` |
| **Smoke test 2/2**: `curl -sf --max-time 60 -X POST https://<api-fqdn>/chat -d '{"userId":"cicd-smoke-test","message":"Hello, this is an automated CI/CD smoke test."}'` | `200` — `{"agent":"FallbackAgent","intent":"UNKNOWN","response":"I could not determine how to help with that. A human may need to assist you.",...}` (generic test message correctly classified as UNKNOWN intent — expected, not a defect) |
| Exact Python JSON-assertion snippet from the `SmokeTests` stage, run against the real captured response body above | `POST /chat: OK (agent=FallbackAgent, intent=UNKNOWN)` — confirms the assertion logic (`response` and `agent` both non-empty) passes against real API output |
| Exact `Stage 8` JUnit-parsing Python snippet, run against a real `pytest --junitxml=...` output (`tests/unit/llm`, 62 tests) | `62 tests, 0 failures, 0 errors, 0 skipped` — confirms the `<testsuites><testsuite>` XML structure and parsing logic are correct against this repo's actual pytest/JUnit output shape |

`python3` is not the correct binary alias in this local Windows dev shell (a pre-existing, unrelated local-environment quirk noted throughout this session — Azure DevOps's `ubuntu-latest` hosted agents have `python3` natively available); the local venv's `python.exe` was used to verify the identical script logic instead.

### Full regression suite (no Python source touched this PBI — required by the PBI's own validation list regardless)

| Command | Result |
|---|---|
| `pytest tests/ -q` | `455 passed, 2 skipped` — identical to PBI-03-06's final count |
| `ruff check apps/api/src src tests ops/scripts` | `All checks passed!` |
| `mypy apps/api/src` | `Success: no issues found in 13 source files` |
| `mypy src` | `Success: no issues found in 102 source files` |

Full transcript archived at `docs/sprint_04/evidence/pbi-04-01-cicd-pipeline-validation.txt`.

Conclusion: PBI-04-01 delivers a complete, internally-consistent, statically-validated Azure DevOps YAML CI/CD pipeline extending the existing Sprint-0 CI foundation — fixing two real, previously-undetected defects along the way (wrong API image build context; stale Bicep module validation list) — plus the minimum new Azure RBAC (two role assignments, zero new resources) required for it to eventually run for real. Every piece of dynamic logic the pipeline depends on (resource-name resolution, smoke-test commands, JUnit parsing) was proven correct against real, live data from the actual DEV environment, not assumed. What remains, by design and pending explicit user approval, is applying the RBAC change to real Azure and creating the Azure DevOps service connection — both are one-time, human, out-of-session actions clearly documented as such, not gaps.

### 2026-08-08 — RBAC deployment to real Azure (explicit user approval obtained after `what-if` review)

| Step | Command | Result |
|---|---|---|
| 1 | `az resource list --resource-group rg-tmx-agent-platform-dev` (pre-check) | All 12 resources present, `Succeeded` |
| 2 | `az deployment group what-if --resource-group rg-tmx-agent-platform-dev --template-file ops/bicep/main.bicep --parameters ops/bicep/parameters/dev.bicepparam` | `10 to modify, 5 no change, 8 unsupported, 1 to ignore`. Zero `+ Create`/`- Delete` at resource level; all `~ Modify` entries were computed-property what-if noise or identically-resolving `reference()` expressions on already-deployed resources; all 8 "Unsupported" diagnostics were `Microsoft.Authorization/roleAssignments` extension resources (documented ARM what-if limitation) — 5 pre-existing, 3 new (AcrPush + 2× Container Apps Contributor) |
| 3 | Change summary presented to user; explicit approval received ("Approved. Proceed with az deployment group create.") | — |
| 4 | `az deployment group create --resource-group rg-tmx-agent-platform-dev --template-file ops/bicep/main.bicep --parameters ops/bicep/parameters/dev.bicepparam` | `provisioningState: Succeeded` |
| 5 | `az identity show --name id-tmxap-dev ... --query principalId` + `az role assignment list --assignee <principalId> --all` | Confirmed 7 Azure-RBAC role assignments total: 4 pre-existing (AcrPull, Key Vault Secrets User, Search Index Data Reader, Cognitive Services OpenAI User) + 3 new (**AcrPush** on `acrtmxapdevl3fgxt`; **Container Apps Contributor** on `ca-tmxap-dev-api`; **Container Apps Contributor** on `ca-tmxap-dev-web`) — all correctly scoped to their individual resources, not the resource group |
| 6 | `az resource list --resource-group rg-tmx-agent-platform-dev` (post-check) | All 12 resources still present, `Succeeded` — none added, none removed |
| 7 | `az containerapp revision list` (api, web) | Active revisions **unchanged**: `ca-tmxap-dev-api--v5`, `ca-tmxap-dev-web--phnq58i` — confirms no new revision was created and no application state was touched, only the new extension role-assignment resources were added |
| 8 | `az containerapp revision list` health check | Both revisions `healthState: Healthy` |
| 9 | `curl https://ca-tmxap-dev-api.../health` | `200 {"status":"ok"}` |

Per explicit user instruction, the Azure DevOps pipeline was **not** triggered in this step.

Conclusion: the RBAC-only change was applied to real Azure with zero impact on any existing resource's identity, configuration, or running state — verified positively (not merely assumed) via role-assignment listing, resource listing, revision-name comparison, health-state check, and a live `/health` call. The Managed Identity is now fully provisioned for the CI/CD pipeline's needs; only the Azure DevOps-side service connection remains before a real pipeline run can be attempted.

## 2026-08-08 — PBI-04-02: Functional Web Chat integration

### Pre-work: read required files, inspect current architecture

| Check | Result |
|---|---|
| Read CLAUDE.md, docs/sprint_04/*; inspect App.tsx, env.ts, apps/web/package.json, apps/web/Dockerfile, vite.config.ts, apps/api/src/main.py, POST /chat contract, CORS config, deployed URLs | Confirmed App.tsx's handleSend only appended a hardcoded local reply (Sprint-0 placeholder, its own welcome text said so); apps/api/src/main.py had zero CORS middleware anywhere (grep confirmed); apps/api/src/config/settings.py had no CORS-related setting to reuse |
| grep _CLAIMS_KEYWORDS/_BROKER_KEYWORDS/_COMMERCIAL_KEYWORDS in src/supervisor/intent.py | Confirmed all 3 required demo phrasings ("I want to report an accident.", "I want to check my commissions.", "I need a commercial insurance quote.") each contain a real matched keyword |
| grep grounder/knowledge_retriever wiring in src/agents/{claims,broker,commercial_intake}_agent.py | Confirmed only ClaimsAgent uses RAG/Grounding — an existing architectural fact, documented, not changed |

### Backend: CORS implementation and validation

| Command | Result |
|---|---|
| pytest tests/unit/api/test_cors.py tests/unit/api/test_chat.py tests/unit/api/test_health.py -v | 17 passed — 6 new CORS tests, 9 existing chat tests, 2 existing health tests, all green on first full run |
| pytest tests/ -q (full suite) | 461 passed, 2 skipped (455 baseline + 6 new CORS tests) |
| ruff check apps/api/src src tests ops/scripts | 1 import-order error in test_cors.py, fixed via ruff check --fix; re-run: All checks passed! |
| mypy apps/api/src / mypy src | Both clean |
| az bicep build --file ops/bicep/main.bicep | exit 0, 0 warnings (confirms the new CORS_ALLOWED_ORIGINS cross-module reference to webContainerApp.outputs.fqdn creates no circular dependency) |
| az bicep build-params — dev/staging/prod | All exit 0 |
| docker compose config | exit 0 |

### Frontend: chat integration and validation

| Command | Result |
|---|---|
| npm run typecheck | Clean |
| npm run lint | Clean |
| npm run build (with the real DEV VITE_API_URL) | Succeeded — dist/assets/index-*.js (~150 KB), confirmed the real API URL baked in via grep |
| npx vitest run (full suite) | 23 passed across 6 files (api/chat.test.ts 4, api/client.test.ts 3, components/MessageArea.test.tsx 5, components/Header.test.tsx 2, components/MessageInput.test.tsx 3, App.test.tsx 6) — one jsdom gap fixed along the way (scrollIntoView not implemented in jsdom; stubbed in setupTests.ts, a standard, environment-only fix) |
| Local vite preview dry-run with the real Azure Container Apps Host header | 200 OK (confirms the pre-existing preview.allowedHosts fix from before this PBI still applies to the newly-built image) |

### Deployment (API + Web images only, no shared infrastructure touched)

| Step | Command | Result |
|---|---|---|
| Pre-check | az resource list --resource-group rg-tmx-agent-platform-dev | All 12 resources present, healthy |
| Build API | az acr build --image tmx-api:dev-20260807205835 --file apps/api/Dockerfile . | Succeeded |
| Build Web | az acr build --image tmx-web:dev-20260807205845-chat --file apps/web/Dockerfile --build-arg VITE_API_URL=... apps/web | Succeeded |
| Deploy API | az containerapp update --name ca-tmxap-dev-api --image ...:dev-20260807205835 --set-env-vars CORS_ALLOWED_ORIGINS=https://ca-tmxap-dev-web... | Succeeded; new revision ca-tmxap-dev-api--0000003, Healthy |
| Verify no env-var loss | az containerapp show --query properties.template.containers[0].env | All 18 pre-existing env vars present unchanged, plus the 1 new CORS_ALLOWED_ORIGINS — confirms --set-env-vars merges, does not replace, the env list |
| Deploy Web | az containerapp update --name ca-tmxap-dev-web --image ...:dev-20260807205845-chat | Succeeded; new revision ca-tmxap-dev-web--0000002, Healthy |

No az deployment group create was run this PBI — both updates were targeted az containerapp update calls, per explicit instruction to rebuild/redeploy only the affected images.

### Live DEV validation (real calls against the real deployed service)

| # | Check | Result |
|---|---|---|
| 1 | GET /health | 200 {"status":"ok"} |
| 2 | CORS preflight (OPTIONS /chat) with Origin: https://ca-tmxap-dev-web... | 200, access-control-allow-origin: https://ca-tmxap-dev-web... (the real deployed Web origin), access-control-allow-methods: GET, POST |
| 3 | GET / (deployed Web page) | 200, real HTML, correct bundle references |
| 4 | Deployed JS bundle content | Contains /chat calls and the real API URL, confirmed via curl + grep directly against the live Container App |
| 5 | Claims turn 1 ("I want to report an accident.", with Origin header matching the real Web origin) | 200 — real gpt-5-mini-2025-08-07 response, 2 real grounded citations (KB-CLAIMS-0002, KB-POLICY-0001), groundingMetadata.isGrounded: true — this single call satisfies both the Claims demo scenario and the RAG/grounded-citation demo scenario |
| 6 | Claims turn 2 (same conversationId, "SYN-POL-0001") | 500 Internal Server Error — reproduced twice with two independent fresh conversations, confirming it is deterministic, not transient. Root-caused via read-only log inspection (az containerapp logs show) to a genuine, pre-existing ToolCallingOrchestrator defect (see decisions.md) — not a CORS or frontend regression from this PBI |
| 7 | Broker turn 1 + turn 2 ("I want to check my commissions." then "SYN-BRK-0001 2026-Q1", same conversationId) | Both 200. Turn 2 returned real Tool-sourced business data (commission_amount: 1250.0, broker_active: true) — proves Broker's deterministic Tool-invocation path is unaffected by the Claims-specific orchestrator defect, and independently proves conversationId persistence works correctly end-to-end |
| 8 | Commercial turn 1 + turn 2 ("I need a commercial insurance quote." then "Acme Consulting LLC", same conversationId) | Both 200 — same confirmation as Broker |

Full transcript archived at docs/sprint_04/evidence/pbi-04-02-web-chat-integration-validation.txt.

### STOP CONDITION accounting

| # | Requirement | Status |
|---|---|---|
| 1 | Deployed DEV Web URL loads successfully | Met — GET / returns 200 with real HTML |
| 2 | Browser can call the deployed DEV API without CORS errors | Met — real preflight + actual-request evidence, correct Access-Control-Allow-Origin for the real Web origin |
| 3 | A real POST /chat response is displayed in the UI | Met for the mechanism (real response received, App.tsx renders result.response/agent/citations — proven via App.test.tsx's mocked-fetch integration tests and the live curl evidence above) |
| 4 | conversationId preserved across multiple turns | Met — proven via Broker and Commercial's real, live 2-turn conversations, plus App.test.tsx's dedicated test for the same mechanism |
| 5 | Claims works end-to-end from the browser | Partially met — a single Claims turn works completely end-to-end (real routing, real LLM response, real grounded RAG citations, correct CORS). A second turn is blocked by the newly-discovered ToolCallingOrchestrator defect (see decisions.md), which is unrelated to this PBI's own changes and explicitly out of scope to fix (src/core/tool_calling/ is forbidden territory for PBI-04-02) |
| 6 | Existing backend tests remain green | Met — 461 passed, 2 skipped (455 baseline + 6 new), zero regressions |

Conclusion: PBI-04-02 delivers a complete, tested, real POST /chat integration replacing the Sprint-0 placeholder, with configuration-driven, non-wildcard CORS enabling genuine cross-origin browser calls between the deployed Web and API Container Apps for the first time. 5 of 6 STOP CONDITION items are fully met; item 5 is honestly reported as partially met, not silently overstated, because live validation surfaced a real, precisely-diagnosed, pre-existing defect in code this PBI was explicitly forbidden from touching. This is the correct, expected outcome of thorough live validation catching a genuine gap in test coverage (every prior automated test used MockLLMProvider, which never exercised the real Azure OpenAI API's message-sequencing constraint) — not a shortfall in this PBI's own delivered scope.

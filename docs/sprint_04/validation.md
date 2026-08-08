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

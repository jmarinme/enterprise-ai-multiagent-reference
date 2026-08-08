# Sprint 04 — Azure DevOps CI/CD Pipeline for the DEV Environment

## Objective

Give the already-deployed, already-operational Azure DEV environment
(`rg-tmx-agent-platform-dev`) a real, automatic Azure DevOps YAML CI/CD pipeline: source
checkout, Python environment setup with caching, quality gates (pytest/ruff/mypy), container
build, push to the existing Azure Container Registry, deployment to the existing DEV Container
Apps only, automated smoke tests, and a deployment summary — extending, not replacing, the
Sprint 0 CI foundation (PBI-00-07).

## Scope

- **PBI-04-01:** extends the existing `azure-pipelines.yml` (created in PBI-00-07) with real
  Continuous Deployment to DEV. Fixes a pre-existing bug in that file (the API image was built
  with the wrong Docker context, predating PBI-03-02's repo-root-context requirement) and a
  stale/incomplete Bicep module validation list (5 modules added by later PBIs were never added
  to Stage 3's validation set). Adds two new, narrowly-scoped RBAC role assignments
  (`AcrPush` on the existing ACR; `Container Apps Contributor` on each existing Container App
  individually) to the platform's existing user-assigned Managed Identity — reused via
  Workload Identity Federation for the new Azure DevOps service connection, not a new identity.
  New pipeline stages: `ContainerBuildAndPush` (build + push, combined for agent/workspace
  continuity — see `decisions.md`), `DeployDev` (targeted `az containerapp update --image`,
  never `az deployment group create`), `SmokeTests` (`GET /health`, `POST /chat` against the
  real deployed DEV API), `DeploymentSummary` (image tags, revisions, deployed apps, execution
  time, test summary, published as a pipeline artifact and build summary).

## Out of scope

- Creating a QA or Production Azure DevOps environment or Azure resource group.
- Redesigning any existing Azure infrastructure (Container Apps Environment, Cosmos DB, Key
  Vault, Azure OpenAI, AI Search, VNet/Private Endpoints, Managed Identity itself).
- Any change to Agent, Supervisor, PromptManager, Tool Calling, or RAG business logic.
- Manual-approval deployment gates, multiple environments, or Azure DevOps "Environment"
  resources — DEV is auto-deployed on every push to the deploy branch, matching this PBI's own
  explicit "automatically deploys" objective; adding approval gates would be scope creep for a
  single, already-approved-for-CI/CD DEV environment.
- Actually creating the Azure DevOps service connection or organization/project configuration —
  this requires Azure DevOps organization access (a PAT/org URL) this session does not have,
  and is inherently a one-time, human, Azure-DevOps-portal action; it is fully documented as a
  PREREQUISITE in both `azure-pipelines.yml`'s own header comment and `decisions.md`.
- ~~Actually applying the two new RBAC role assignments to the real Azure DEV environment~~ —
  **done as a follow-up, explicitly-approved action after this PBI's own summary**: `az
  deployment group what-if` was reviewed (zero creates/deletes/replacements confirmed), the
  change summary was shown to the user, explicit approval was given, and `az deployment group
  create` was run. All three new role assignments (AcrPush; Container Apps Contributor × 2)
  verified present; all 12 existing resources verified still healthy with unchanged Container
  App revisions. See `decisions.md`'s "RBAC additions applied to the real DEV environment"
  entry and `validation.md` for full evidence. The Azure DevOps pipeline itself was
  deliberately **not** triggered as part of this follow-up.
- Actually triggering a real Azure DevOps pipeline run — no Azure DevOps org/PAT is configured
  in this environment; validated via YAML syntax parsing, a full manual schema/logic review
  against the working Sprint-0 baseline, and real (read-only) `az` CLI dry-runs of every
  dynamic-resolution query and smoke-test command the pipeline uses, against the actual live
  DEV environment.

## Deliverables

- [x] PBI-04-01: Azure DevOps CI/CD Pipeline for the TMX Agent Platform DEV Environment.
- [x] PBI-04-02: Functional Web Chat integration (COMPLETE WITH CONDITIONS — see Deliverable Log).

## Acceptance criteria

| ID | Criterion | Evidence expected |
|---|---|---|
| AC-01 | Azure DevOps YAML pipeline created (no Classic Pipelines) | `azure-pipelines.yml` — single YAML file, `stages:`-based |
| AC-02 | Automatic build (source checkout, Python environment, package caching) | `azure-pipelines.yml` — `BackendQuality`/`FrontendQuality` stages, `Cache@2` tasks |
| AC-03 | Automatic tests (pytest, ruff, mypy); pipeline fails immediately on any failure | `azure-pipelines.yml` — `BackendQualityJob` steps, each with `set -e`, no `continueOnError` |
| AC-04 | Automatic Docker build (API + Web, using the existing Dockerfiles) | `azure-pipelines.yml` — `ContainerBuildAndPush` stage; real bug fix (API build context) documented in `decisions.md` |
| AC-05 | Automatic push to the existing ACR (no new registry) | `azure-pipelines.yml` — `az acr login` + `docker push`, ACR resolved dynamically via `az acr list` against the existing resource group |
| AC-06 | Automatic deployment to the existing DEV Container Apps only (no infra recreation, image versioning not `latest`) | `azure-pipelines.yml` — `DeployDev` stage, `az containerapp update --image <repo>:dev-$(Build.BuildId)`, never `az deployment group create` |
| AC-07 | Automatic smoke tests (`GET /health`, `POST /chat`); pipeline fails if they fail | `azure-pipelines.yml` — `SmokeTests` stage, `curl -f` + JSON-shape assertion; real dry-run evidence in `validation.md` |
| AC-08 | Deployment summary published (image tags, revision, deployed apps, execution time, test summary) | `azure-pipelines.yml` — `DeploymentSummary` stage, `deployment-summary` pipeline artifact |
| AC-09 | Existing Azure infrastructure reused — no new ACR/Container Apps Environment/Cosmos DB/Key Vault/Azure OpenAI/Managed Identity | Code review — only 2 new `Microsoft.Authorization/roleAssignments` resources added to Bicep, scoped to existing resources; zero new top-level resources |
| AC-10 | No regression to existing tests or the Sprint-0 CI stages | `pytest`/`ruff`/`mypy` evidence unchanged (455 passed, 2 skipped); `BackendQuality`/`FrontendQuality`/`InfrastructureValidation` stages preserved, not removed |
| AC-11 | Secure service connection (Workload Identity Federation, no stored secret) and Managed Identity reuse | `azure-pipelines.yml` header comment PREREQUISITE section; `decisions.md`'s RBAC-addition writeup |
| AC-12 | Hardcoded resource names avoided where possible | Code review — only the resource group name (`rg-tmx-agent-platform-dev`, stable/non-generated) is a literal; ACR name, Container App names, and FQDNs are all resolved dynamically at pipeline-run time via `az ... list/show` queries |
| AC-13 | Bicep RBAC additions validate cleanly (`az bicep build`/`build-params`) | `validation.md` — all exit 0, 0 warnings |
| AC-14 | Pipeline YAML validated (syntax + dry-run) | `validation.md` — Python `yaml.safe_load` parse, manual schema review, real read-only `az` CLI dry-runs of every dynamic query and smoke-test command against the live DEV environment |
| AC-15 | CORS is configuration-driven, allows the deployed Web origin, never `"*"` | `apps/api/src/config/settings.py`/`main.py`; `ops/bicep/main.bicep`'s `CORS_ALLOWED_ORIGINS` env var; `tests/unit/api/test_cors.py` (6 tests); live preflight evidence in `validation.md` |
| AC-16 | Existing API behavior preserved; no Agent/Supervisor/Tools/RAG/PromptManager/LLMProvider/Cosmos/infrastructure code touched | Code review — `git status` shows only `apps/api/src/{main.py,config/settings.py}`, `apps/web/**`, `ops/bicep/main.bicep`'s one new env-var line, and docs; full backend suite unchanged pass count plus 6 new CORS tests |
| AC-17 | Placeholder client-side chat logic replaced with a real `POST /chat` integration | `apps/web/src/api/chat.ts`, `apps/web/src/App.tsx` |
| AC-18 | Multi-turn conversation via `conversationId`; "New conversation" resets state | `apps/web/src/App.test.tsx`; live Broker/Commercial 2-turn evidence in `validation.md` (Claims 2nd turn blocked by the discovered `ToolCallingOrchestrator` defect — see `decisions.md`) |
| AC-19 | Loading/sending state; disabled send button while in flight; safe error display; retry-friendly | `apps/web/src/components/MessageInput.tsx`, `apps/web/src/App.tsx`, `apps/web/src/App.test.tsx` |
| AC-20 | Response metadata rendered (agent, intent via badge, citations, grounding status, safe tool-call info) — only fields the real contract defines | `apps/web/src/components/MessageArea.tsx`, `apps/web/src/api/chat.ts`, `apps/web/src/components/MessageArea.test.tsx` |
| AC-21 | UI stays simple, uses existing visual structure, explains the three capabilities without hardcoded per-agent screens | `apps/web/src/components/Sidebar.tsx` (example prompts + "New conversation", reusing the existing sidebar element) |
| AC-22 | Frontend tests cover request mapping, first-turn, follow-up, rendering, citations, errors, loading, reset | `apps/web/src/api/chat.test.ts`, `apps/web/src/App.test.tsx`, `apps/web/src/components/MessageArea.test.tsx` — 23 tests total, all passing |
| AC-23 | Only API/Web Container App images rebuilt/redeployed with versioned tags; no shared infrastructure recreated | `validation.md` — `az acr build` + `az containerapp update`, no `az deployment group create` |
| AC-24 | Live DEV STOP CONDITION items 1-3, 6 fully met; item 4 fully met via Broker/Commercial; item 5 (Claims) met for a single turn, blocked for multi-turn by a discovered, out-of-scope defect | `validation.md`'s STOP CONDITION accounting |

## Dependencies

- Sprint 0's CI foundation (`azure-pipelines.yml`, PBI-00-07) and its documented, disabled
  `Deploy_Dev` stage, whose intended flow this PBI implements and enables.
- Sprint 03's completed, operational Azure DEV deployment (`rg-tmx-agent-platform-dev`,
  PBI-03-05/PBI-03-06) — this PBI deploys to that exact environment, unchanged, and depends on
  `POST /chat` already returning `200` against the real deployed service (PBI-03-06's own stop
  condition) for the smoke tests to be meaningful.
- `docs/sprint_00/security-baseline.md` §6's already-documented Workload Identity Federation
  recommendation, implemented for the first time by this PBI.

## Risks

| Risk | Probability | Impact | Mitigation |
|---|---:|---:|---|
| No Azure DevOps organization/PAT available in this session to create the service connection or trigger a real pipeline run | Realized | Medium | Fully documented as a one-time PREREQUISITE in `azure-pipelines.yml`'s header and `decisions.md`; every dynamic query and smoke-test command the pipeline uses was dry-run (read-only) against the real, live DEV environment to de-risk the logic before a real run is ever attempted |
| The two new RBAC role assignments are not yet applied to the real Managed Identity — the pipeline cannot authenticate/push/deploy until they are | Realized (deliberate) | Medium | Bicep changes validated statically (`az bicep build`); applying them (`az deployment group create`) requires explicit user approval, per this PBI's own narrower "Validation" scope (no live Azure deployment listed, unlike PBI-03-05/06) |
| `az containerapp update --image` on the same textual tag is a no-op (discovered the hard way in PBI-03-05/06's manual validation) | Avoided by design | Would have been High | Every pipeline run uses a genuinely unique tag (`dev-$(Build.BuildId)`), so this class of bug cannot recur — no `--revision-suffix` workaround needed |
| Stale/incomplete Bicep module list in Stage 3 (5 modules added since PBI-00-07 were never added to validation) | Realized, now fixed | Was Medium | `bicepModuleFiles` parameter list corrected to match `ops/bicep/modules/*.bicep` exactly (14 modules + main.bicep), verified via `ls` |
| Combining "Container Build" and "Push Images" into one YAML stage instead of two, per the user's literal 8-item stage list | Accepted deliberately | Low | Documented rationale in `azure-pipelines.yml`'s own comment and `decisions.md`: Azure Pipelines stages do not share a Docker image cache across stage boundaries; splitting them would require a save/publish/download roundtrip with no benefit for this DEV-only, non-approval-gated flow |

## Deliverable Log

<!-- Append entries. Do not remove previous entries. -->

PBI-04-01: See `decisions.md` and `validation.md` for the full writeup. Summary: extended the existing Sprint-0 `azure-pipelines.yml` (not a new parallel file) with 5 new/replaced stages implementing real, automatic CI/CD to the existing DEV environment — `ContainerBuildAndPush` (fixes a real, pre-existing API-image build-context bug; builds and pushes both images to the existing ACR using a unique `dev-$(Build.BuildId)` tag), `DeployDev` (targeted `az containerapp update --image` against the existing Container Apps only, never `az deployment group create`), `SmokeTests` (`GET /health`, `POST /chat`, fails the pipeline on any failure), and `DeploymentSummary` (image tags/revisions/deployed apps/execution time/test summary, published as a pipeline artifact and build summary). Added two new, narrowly-scoped RBAC role assignments to `ops/bicep/main.bicep`/`container-registry.bicep`/`container-app.bicep` (AcrPush on the existing ACR; Container Apps Contributor on each existing Container App individually) granted to the platform's existing Managed Identity — reused via Workload Identity Federation, no new identity, no stored credential — validated statically (`az bicep build`, all exit 0, 0 warnings) but NOT yet applied to real Azure, pending explicit user approval. Every dynamic resource-name resolution query and both smoke-test commands were dry-run (read-only) against the real, live DEV environment and confirmed correct. 455 tests pass unchanged; ruff and mypy clean. No Agent, Supervisor, PromptManager, Tool Calling, or RAG code touched; no new Azure resource beyond the two RBAC role assignments; no QA/Prod environment created. — 2026-08-08
Evidence: `docs/sprint_04/evidence/pbi-04-01-cicd-pipeline-validation.txt`

PBI-04-02: Turned the Sprint-0 placeholder Web UI into a real, working multi-turn chat client against the existing DEV `POST /chat` API. **Backend (minimum necessary change):** `apps/api/src/config/settings.py` gained `cors_allowed_origins`/`cors_allowed_origins_list`; `apps/api/src/main.py` wires `CORSMiddleware` (outermost layer, configuration-driven, never `"*"`, `allow_credentials=False`); `ops/bicep/main.bicep`'s API Container App gained a `CORS_ALLOWED_ORIGINS` env var resolved dynamically from `webContainerApp.outputs.fqdn` — no Agent/Supervisor/Tools/RAG/PromptManager/LLMProvider/Cosmos/infrastructure code touched, confirmed by `git status`. **Frontend:** new `apps/web/src/api/chat.ts` (typed `POST /chat` client matching the real contract exactly), `apps/web/src/utils/userId.ts` (synthetic per-browser id, localStorage-persisted), and a rewritten `App.tsx` replacing the hardcoded placeholder reply with real API calls — `conversationId` state (absent on turn 1, returned and reused on every following turn), loading/disabled-send state, a generic safe error message with a working Retry action (never a raw exception/status), and a "New conversation" reset. `MessageArea.tsx` gained an agent badge, citation cards, a grounding badge, safe tool-call badges (`toolName`/`success` only — never raw `data`/`error` text), a typing indicator, and scroll-to-latest; `Sidebar.tsx` was repurposed (not replaced with a new element) into a "New conversation" action plus four real, already-proven example prompts (one per Claims/Broker/Commercial capability, plus a Claims question chosen to also demonstrate grounded RAG citations) — no hardcoded per-Agent screens; the Supervisor still decides routing. 23 new/updated frontend tests (`chat.test.ts`, `App.test.tsx`, `MessageArea.test.tsx`, updated `MessageInput.test.tsx`) plus 6 new backend CORS tests (`test_cors.py`) — full suite: 461 backend tests passed (2 skipped), 23 frontend tests passed; typecheck/lint/build all clean. **Deployment:** only the API and Web Container App images were rebuilt (`az acr build`, versioned `dev-<timestamp>` tags) and updated in place (`az containerapp update --image` [+ `--set-env-vars` for the API's CORS origin]) — confirmed via a full env-var diff that the pre-existing 18 API env vars were preserved, not wiped; no Resource Group/Container Apps Environment/Azure OpenAI/Cosmos/Key Vault/Managed Identity/ACR/AI Search/networking recreated. **Live validation** (see `validation.md` for full evidence) confirmed `GET /health` 200, a real CORS preflight from the actual deployed Web origin succeeding with the correct `Access-Control-Allow-Origin`, the Web page loading (still no "host not allowed", carried forward from the pre-PBI-04-02 Vite fix), the deployed JS bundle correctly wired to `/chat` and the real API URL, and — critically — live multi-turn validation against the real `gpt-5-mini` deployment surfaced a genuine, pre-existing defect in `ToolCallingOrchestrator.run()` (missing assistant `tool_calls` message before the tool-result message; real Azure OpenAI rejects the malformed sequence) that blocks a *second* Claims turn specifically whenever the LLM decides to call a tool — discovered, precisely diagnosed, and documented in `decisions.md`, but **not fixed**, since `src/core/tool_calling/` is explicitly out of this PBI's authorized scope ("Do not modify... Tools..."). Broker and Commercial each completed a full, real 2-turn conversation successfully (proving both the deterministic Tool-invocation path and `conversationId` persistence work correctly), and Claims' own first turn succeeded with real grounded RAG citations rendered correctly. STOP CONDITION items 1, 2, 3, 4 (via Broker/Commercial), and 6 are fully met; item 5 (Claims end-to-end) is met for a single turn only — honestly reported as COMPLETE WITH CONDITIONS rather than silently claimed as fully met. — 2026-08-08
Evidence: `docs/sprint_04/evidence/pbi-04-02-web-chat-integration-validation.txt`

## Sprint validation

See `validation.md`.

## Sprint retrospective

Complete when closing the sprint:

- What worked:
- What did not:
- Technical debt:
- Security findings:
- Follow-up PBIs:

# TMX Enterprise AI Reference Platform — Deployment Guide

**Document version:** 1.0 — 2026-08-11 (PBI-10-03)
**Status:** Reflects the DEV environment as actually deployed and validated in this repository as of this date.

---

## 1. Purpose

### 1.1 Purpose of this guide

This document describes the **actual, implemented** deployment process for the TMX Enterprise AI
Reference Platform: how its infrastructure is provisioned, how its two applications (API and Web)
are built and released, how a release is validated, and how a release can be rolled back. Every
statement in this guide is backed by a specific file, command, or sprint decision record in this
repository. Where a detail could not be confirmed from repository evidence, this guide says so
explicitly rather than presenting an assumption as fact.

### 1.2 Scope

In scope: infrastructure-as-code (Bicep), the CI/CD pipeline (`azure-pipelines.yml`), the
application build/deploy workflow, runtime configuration, deployment validation, rollback, and
known constraints — all as implemented in this repository today. Out of scope: application
feature behavior (covered by the architecture documentation and ADRs), and any deployment target
other than the single DEV environment this repository has actually provisioned.

### 1.3 Intended audience

Engineers who need to deploy, operate, validate, or troubleshoot this platform — including a
future maintainer with no prior exposure to this specific repository, and the academic evaluators
of this project.

### 1.4 Supported environment(s)

- **DEV** (`rg-tmx-agent-platform-dev`): the only environment that has been actually deployed and
  live-validated as of this document's date. All command examples, evidence, and troubleshooting
  entries in this guide reference DEV.
- **staging / prod**: parameter files exist (`ops/bicep/parameters/staging.bicepparam`,
  `ops/bicep/parameters/prod.bicepparam`) and are compiled/validated by the CI/CD pipeline's
  Infrastructure Validation stage on every run, but **no staging or production resource group has
  been deployed**. Any reference to staging/prod in this guide is explicitly marked as
  configuration that exists but has not been exercised against real Azure resources.

### 1.5 Academic project disclaimer

Per `CLAUDE.md` §1, this repository is an academic reference implementation for a corporate
insurance multi-agent solution. It does **not** represent an officially approved TMX production
architecture, uses only synthetic data and simulated business APIs, and must never be treated as
containing real internal systems, real customer information, or production credentials. This
deployment guide documents the DEV deployment of that reference implementation — nothing in this
guide should be read as production deployment guidance without the hardening steps explicitly
identified as deferred in Section 12.

---

## 2. Solution Overview

The platform is a multi-agent conversational system for a synthetic insurance business, built
from two deployable applications and a set of managed Azure backing services.

| Component | Role | Implementation evidence |
|---|---|---|
| **React Web Application** | Chat UI the end user interacts with; calls the API over HTTPS. | `apps/web/` (React + TypeScript + Vite); `apps/web/Dockerfile` |
| **FastAPI Backend** | HTTP transport layer; exposes `POST /chat`, `GET /health`, `GET /ready`, and conversation-history endpoints. | `apps/api/src/main.py`, `apps/api/src/api/` |
| **Supervisor Agent** | Validates context, resolves intent deterministically, routes to a domain Agent, persists conversation state. | `src/supervisor/orchestrator.py`; see [ADR-0007](adr/0007-ai-governance-boundary.md) |
| **Claims Agent** | Guides a synthetic after-hours claim notification flow through approved Tools. | `src/agents/claims_agent.py`, `src/agents/claims/` |
| **Broker Services Agent** | Synthetic policy/procedure/receipt/commission queries. | `src/agents/broker_agent.py`, `src/agents/broker/` |
| **Commercial Intake Agent** | Synthetic commercial lead classification and preregistration. | `src/agents/commercial_intake_agent.py` |
| **Azure OpenAI** | LLM backing the platform's language understanding and response generation (`gpt-5-mini`). | `ops/bicep/modules/azure-openai.bicep`; `src/llm/azure_openai_provider.py` |
| **Azure AI Search** | Provisioned as infrastructure; **not currently used at runtime** — the deployed API uses the local `KnowledgeProvider` (see Section 8). | `ops/bicep/modules/ai-search.bicep`; `src/rag/azure_ai_search_provider.py` |
| **Cosmos DB** | Conversation history persistence, partitioned by `userId`. | `ops/bicep/modules/cosmos-db.bicep`; see [ADR-0004](adr/0004-conversation-store-selection.md) |
| **Azure Container Apps** | Hosting runtime for both the API and Web applications. | `ops/bicep/modules/container-app.bicep`; see [ADR-0005](adr/0005-application-hosting-strategy.md) |

### 2.1 High-level deployment flow

```
Developer pushes to main
        │
        ▼
Azure DevOps Pipeline (azure-pipelines.yml)
        │
        ├─ 1. Quality gates (backend pytest/ruff/mypy, frontend lint/typecheck/test/build)
        ├─ 2. Security gates (pip-audit, npm audit, detect-secrets)
        ├─ 3. Build container images (docker build, repo-root context for API)
        ├─ 4. Push images to Azure Container Registry (commit-SHA-traceable tags)
        ├─ 5. Infrastructure: validate + apply ops/bicep/main.bicep (idempotent, additive)
        ├─ 6. Deploy DEV: az containerapp update (image reference only — no infra recreation)
        └─ 7. Smoke tests: /health, POST /chat (Claims scenario), correlation ID, continuity
        │
        ▼
Live DEV Container Apps (API + Web) serving the updated revision
```

This flow is implemented in full in `azure-pipelines.yml` and is described in detail in
Sections 6, 7, and 11 below.

---

## 3. Deployment Architecture

### 3.1 Current implementation (deployed and validated in DEV)

All resources below are declared in `ops/bicep/main.bicep` and its modules, and are live in
`rg-tmx-agent-platform-dev`.

| Resource | Bicep module | Purpose |
|---|---|---|
| Resource Group | `rg-tmx-agent-platform-dev` (pre-existing target, not created by this template) | Container for every resource below. |
| Log Analytics Workspace | `modules/log-analytics.bicep` | Central log sink for Application Insights and Container Apps. |
| Application Insights | `modules/app-insights.bicep` | APM/telemetry; connection string stored in Key Vault (`appinsights-connection-string`). |
| Managed Identity | `modules/managed-identity.bicep` | Single, shared user-assigned identity (`id-tmxap-dev`) used by both Container Apps for RBAC-gated access to every other data-plane resource. |
| Azure Container Registry | `modules/container-registry.bicep` | Stores `tmx-api`/`tmx-web` images; `AcrPull`-gated, `adminUserEnabled: false`. |
| Key Vault | `modules/key-vault.bicep` | RBAC-authorized secret store; currently holds the App Insights connection string secret. |
| Cosmos DB (NoSQL) | `modules/cosmos-db.bicep` | Conversation store, `disableLocalAuth: true`, Serverless capacity, partitioned by `/userId`. See [ADR-0004](adr/0004-conversation-store-selection.md). |
| Azure AI Search | `modules/ai-search.bicep` | Provisioned (Free tier, `eastus`); not wired into the runtime KnowledgeProvider selection today (see Section 8). |
| Azure OpenAI | `modules/azure-openai.bicep` | `gpt-5-mini` chat deployment, `S0` SKU. |
| Container Apps Environment | `modules/container-apps-environment.bicep` | Shared Consumption-plan environment hosting both Container Apps. |
| API Container App | `modules/container-app.bicep` (instance `apiContainerApp`) | Runs the FastAPI backend; `activeRevisionsMode: 'Single'`. |
| Web Container App | `modules/container-app.bicep` (instance `webContainerApp`) | Runs the React frontend; `activeRevisionsMode: 'Single'`. |
| Action Group | `modules/monitor-alerts.bicep` (`actionGroup`) | Alert notification target (email, when `alertEmailAddress` is set). |
| Metric Alerts | `modules/monitor-alerts.bicep` (`errorRateAlert`, `latencyAlert`, `availabilityAlert`) | Application Insights-backed alert rules on the API Container App. |

### 3.2 Provisioned but not exercised at runtime in DEV

- **Azure AI Search**: the resource exists, but `dev.bicepparam` sets `knowledgeProvider = 'local'`
  — the deployed API uses `LocalKnowledgeProvider`, not `AzureAISearchProvider`. Documented
  directly in `dev.bicepparam`'s own comment: "no AI Search index exists yet (out of scope)."
- **VNet / Private Endpoints**: modules exist (`modules/virtual-network.bicep`,
  `modules/private-endpoint.bicep`, `modules/private-dns-zone.bicep`) but are conditionally
  deployed only `if (enablePrivateNetworking)`, which is `false` in `dev.bicepparam`. See
  [ADR-0001](adr/0001-networking-posture-and-vnet-deferral.md) and
  [ADR-0002](adr/0002-vnet-private-endpoints-hardening.md).

### 3.3 Future architecture (not deployed)

- **Azure Functions Tool Layer + Durable Functions workflow engine**
  (`modules/function-app.bicep`, `modules/storage-account.bicep`): gated behind
  `deployServerlessToolLayer` (default `false`). Not deployed in DEV — this subscription has
  confirmed zero deployable `Microsoft.Web` App Service quota (3 independent real deployment
  attempts). See [ADR-0003](adr/0003-azure-functions-tool-and-workflow-layer.md) and Section 12.
- **Azure Front Door / Application Gateway / WAF**: not present anywhere in `ops/bicep/`. Both
  Container Apps remain directly, publicly reachable via their own
  `*.azurecontainerapps.io` ingress. See [ADR-0002](adr/0002-vnet-private-endpoints-hardening.md).
- **User-facing Microsoft Entra ID authentication**: CLAUDE.md §4.5 specifies Entra ID/OAuth2/OIDC
  for the frontend. No such implementation exists in `apps/web/` (no MSAL/OIDC library in
  `package.json`) or `apps/api/` (no auth middleware/JWT validation in `apps/api/src/api/`). See
  Section 12 for the explicit deferral statement.

---

## 4. Deployment Prerequisites

Verified against what the repository's own tooling and pipeline actually require.

| Prerequisite | Why it's required | Evidence |
|---|---|---|
| Azure Subscription with Owner/Contributor access to the target resource group | Provisions every resource in Section 3.1. | `ops/bicep/main.bicep` |
| Azure CLI (`az`), including the `bicep` extension | Used for every `az deployment group`/`az containerapp`/`az acr` command in this guide. | `azure-pipelines.yml` (`az bicep install`, `AzureCLI@2` tasks) |
| Git | Repository access, branch-based workflow. | CLAUDE.md §15 |
| Python 3.12 | Runs the API locally and the backend test suite. | `apps/api/Dockerfile` (`FROM python:3.12-slim`), CLAUDE.md §5 |
| Node.js 20.x | Builds and tests the React frontend. | `azure-pipelines.yml` (`nodeVersion: '20.x'`), `apps/web/Dockerfile` (`FROM node:20-alpine`) |
| Docker (or `az acr build` as a remote-build fallback) | Builds both container images. | `apps/api/Dockerfile`, `apps/web/Dockerfile`; `docs/sprint_03/validation.md` documents a real session where local Docker was unavailable and `az acr build` was used instead (see Section 13). |
| Azure DevOps project access + the `sc-tmx-agent-platform-dev` service connection | Required for any pipeline-driven (as opposed to manual) deployment. | `azure-pipelines.yml` header comment, `docs/sprint_07/azure-devops-setup.md` |
| An Azure OpenAI model deployment approved in the target region | The `azure-openai.bicep` module deploys `gpt-5-mini`; quota/model availability must exist in the chosen region. | `docs/sprint_03/decisions.md` (documents a real `gpt-4o-mini` deprecation issue during initial deployment — see Section 13) |

**Not required today**: Kubernetes/`kubectl`/Helm (no AKS in this architecture — see
[ADR-0005](adr/0005-application-hosting-strategy.md)); Terraform (Bicep is this platform's only
IaC tool per CLAUDE.md §5); a self-hosted build agent (the pipeline uses Microsoft-hosted
`ubuntu-latest` agents — see Section 11 for the one open constraint on this).

---

## 5. Repository Structure

Deployment-relevant folders only (see `CLAUDE.md` §6 for the complete repository standard).

| Path | Contents | Relevance to deployment |
|---|---|---|
| `apps/api/` | FastAPI transport layer (`src/`), `Dockerfile`, `pyproject.toml` | Built into the `tmx-api` image. Its `Dockerfile` build context is the **repo root**, not `apps/api/` itself — required because it also `COPY`s the shared `src/` domain library (see `apps/api/Dockerfile`'s own header comment). |
| `apps/web/` | React frontend, `Dockerfile`, `package.json` | Built into the `tmx-web` image. `VITE_API_URL` is a Docker build-arg baked in at build time (Vite inlines `VITE_*` vars at build, not at container runtime — `docs/sprint_00/decisions.md`, PBI-00-03). |
| `src/` | Reusable domain library (agents, supervisor, tools, providers) | Copied into the API image (`COPY src ./src`) — never shipped standalone; it is not independently deployable. |
| `configs/prompts/`, `configs/knowledge_base/` | Versioned prompts and local RAG documents | Copied into the API image alongside `src/`. |
| `ops/bicep/` | `main.bicep`, `modules/*.bicep`, `parameters/{dev,staging,prod}.bicepparam` | The complete infrastructure-as-code definition — see Section 6. |
| `ops/functions/` | Azure Functions Tool Layer source (Claims) | Exists, tested, **not deployed** in DEV (`deployServerlessToolLayer=false`) — see Section 12. |
| `ops/scripts/` | Operational PowerShell scripts | Linted by the pipeline (`ruff check ... ops/scripts`); not part of the container images. |
| `azure-pipelines.yml` + `azure-pipelines/templates/steps/*.yml` | The CI/CD pipeline definition | See Sections 6, 7, 11. |
| `docker-compose.yml` | Local multi-container development | Not used by the Azure deployment path; local-only convenience. |
| `docs/Architecture/` | ADRs, this Deployment Guide | Living, cross-sprint architecture documentation. |
| `docs/sprint_NN/` | Per-sprint evidence, decisions, validation records | The evidentiary source for most of this guide's "actually happened" claims (deployment attempts, real errors, real fixes). |
| `tests/` | `unit/`, `integration/`, `conversational/`, `e2e/` | Executed by the pipeline's Quality stage (Section 11); not part of any deployed artifact. |

---

## 6. Infrastructure Deployment

### 6.1 Bicep templates

`ops/bicep/main.bicep` is the single entry-point template; it declares every resource in
Section 3.1 (plus the conditionally-gated ones in 3.2/3.3) and composes them from the 18 reusable
modules under `ops/bicep/modules/`. It is designed to be idempotent and additive — re-running it
against an already-deployed resource group updates only what changed, and (per
`docs/sprint_07/decisions.md` and the pipeline's own error-handling logic) a failure in one
conditionally-gated module (the Function App) does not prevent ARM from applying every other,
independent resource in the same deployment.

### 6.2 Parameter files

Three environment-specific parameter files exist, all `using '../main.bicep'`:

- `ops/bicep/parameters/dev.bicepparam` — the only one actually deployed. Conservative/low-cost
  choices throughout: Free-tier AI Search, Serverless Cosmos, single-replica Container Apps,
  `enablePrivateNetworking=false`, `deployServerlessToolLayer=false`.
- `ops/bicep/parameters/staging.bicepparam`, `ops/bicep/parameters/prod.bicepparam` — compiled and
  validated by CI on every pipeline run, but **never deployed against a real resource group**. Any
  values in these files are configuration-as-written, not configuration-as-validated.

### 6.3 Validation

Two distinct validation mechanisms exist, both real, both run by the pipeline:

- **`az bicep build --file <path> --stdout`** — pure offline compilation of one `.bicep` file at a
  time (every module plus `main.bicep`). No Azure login, no deployment. Purpose: catch syntax and
  type errors before anything is sent to Azure. Implemented in
  `azure-pipelines/templates/steps/bicep-build.yml`, run for every file listed in the pipeline's
  `bicepModuleFiles` parameter, on **every** pipeline run (PR, feature branch, or `main`).
- **`az deployment group validate --resource-group <rg> --template-file ops/bicep/main.bicep
  --parameters ops/bicep/parameters/dev.bicepparam`** — a live, authenticated ARM preflight check
  against the real resource group: confirms the deployment *would* succeed (parameter values
  resolve, RBAC references are valid, resource providers are registered) without actually
  provisioning anything. Runs only on `main` pushes (`isDeployRun`), immediately before the real
  deployment.

### 6.4 Resource deployment

```
az deployment group create \
  --resource-group rg-tmx-agent-platform-dev \
  --name "pipeline-infra-<Build.BuildId>" \
  --template-file ops/bicep/main.bicep \
  --parameters ops/bicep/parameters/dev.bicepparam
```

This is the exact command the pipeline's `InfrastructureDeploy` stage runs (verbatim from
`azure-pipelines.yml`). Purpose: apply the validated template for real — create or update every
resource in Section 3.1 to match the current `main.bicep`/`dev.bicepparam` state. Per CLAUDE.md
§7.1, this command belongs to the CI/CD pipeline in normal operation; a manual, one-off
infrastructure-only run by an engineer is the documented exception, not the default path, and
requires explicit authorization per action.

**Command purpose summary**

| Command | Purpose | Azure login required | Runs on |
|---|---|---|---|
| `az bicep build` | Offline syntax/type validation of one file | No | Every push/PR |
| `az deployment group validate` | Live ARM preflight against the real resource group | Yes | `main` pushes only |
| `az deployment group create` | Actually provision/update resources | Yes | `main` pushes only |

---

## 7. Application Deployment

This is a **container-image deployment to Azure Container Apps** — there is no Kubernetes
manifest, Helm chart, or cluster of any kind in this platform (see
[ADR-0005](adr/0005-application-hosting-strategy.md)).

### 7.1 Build

- **API image** (`tmx-api`): built with `apps/api/Dockerfile`, **repo-root build context**
  (`docker build --file apps/api/Dockerfile .`) — required because the image also packages the
  shared `src/` domain library and `configs/prompts`/`configs/knowledge_base`, all of which live
  outside `apps/api/`.
- **Web image** (`tmx-web`): built with `apps/web/Dockerfile`, context `apps/web` —
  `VITE_API_URL` is passed as a `--build-arg`, resolved dynamically by the pipeline to the live
  API Container App's own FQDN (`https://<api-fqdn>`) at build time.
- **Web-only-when-changed**: the pipeline diffs `apps/web/` against the parent commit
  (`git diff --name-only HEAD^ HEAD -- apps/web`) and skips the Web build/push/deploy entirely
  when nothing under that path changed — the API is always rebuilt and redeployed on every `main`
  push.

### 7.2 Azure Container Registry

Both images are pushed to the single ACR provisioned by `modules/container-registry.bicep`
(`Basic` SKU in DEV, `adminUserEnabled: false` — pull/push is RBAC-gated, `AcrPull` for the
Container Apps' Managed Identity, and the pipeline's own service-connection principal for push).
The registry name and login server are resolved dynamically at pipeline runtime
(`az acr list --resource-group ... --query "[0].name"`) — never hardcoded, so a template
redeploy that changes the generated resource name suffix never requires a pipeline edit.

### 7.3 Image tagging strategy

`imageTag: 'dev-$(Build.BuildId)-$(Build.SourceVersion)'` — every image tag encodes the Azure
DevOps build number and the full Git commit SHA. **`latest` is never used.** This means:

- Every deployed image maps back to an exact commit without cross-referencing build history.
- Every previously-pushed image remains individually addressable in ACR indefinitely (subject to
  registry retention policy, which this template does not currently configure), which is the
  mechanism the rollback strategy in Section 10 depends on.

### 7.4 Container App update

```
az containerapp update \
  --name <api-app-name> \
  --resource-group rg-tmx-agent-platform-dev \
  --image <acr-login-server>/tmx-api:<imageTag>
```

(and the equivalent for `tmx-web`, only when Web changed). This is the pipeline's `DeployDev`
stage, verbatim. It updates **only the container image reference** on the already-existing
Container App — it never runs `az deployment group create`/`what-if` and never touches Cosmos DB,
Key Vault, Azure OpenAI, AI Search, the Managed Identity, or the registry's own management plane.
The API and Web Container App names are resolved dynamically
(`az containerapp list --query "[?ends_with(name, '-api')]..."`), not hardcoded.

### 7.5 Revisions

Both Container Apps are configured with **`activeRevisionsMode: 'Single'`**
(`ops/bicep/modules/container-app.bicep`): exactly one revision serves 100% of traffic at any
time. Every `az containerapp update --image ...` call creates a genuine new revision (the image
tag is always unique per pipeline run, so Container Apps never needs a `--revision-suffix`
workaround) and Azure Container Apps automatically activates it once healthy.

### 7.6 Traffic management

Because `activeRevisionsMode` is `Single`, there is no traffic-splitting between revisions in
this deployment model — the newest healthy revision always receives 100% of traffic. (Container
Apps' `Multiple` revision mode, which supports weighted traffic splits across concurrently active
revisions, is **not** configured anywhere in this repository.) A prior, deactivated revision
remains present (not deleted) and has been directly observed in practice — see Section 10.

---

## 8. Runtime Configuration

The following is DEV's actual, currently validated runtime configuration
(`ops/bicep/parameters/dev.bicepparam`):

| Setting | Value | Why |
|---|---|---|
| `deployServerlessToolLayer` | `false` | This subscription has confirmed **zero** deployable `Microsoft.Web` App Service quota — 3 independent real `az deployment group create` attempts (`Y1`, `B1`, `P0v4`) all failed identically with `SubscriptionIsOverQuotaForSku`. Rather than have every pipeline run re-attempt (and re-fail) provisioning the Function App and its dedicated Storage Account, this flag gates both out of the DEV deployment entirely. See [ADR-0003](adr/0003-azure-functions-tool-and-workflow-layer.md). |
| `TOOL_PROVIDER` (`toolProvider` param) | `inprocess` | With `deployServerlessToolLayer=false`, no Azure Functions endpoint exists for `AzureFunctionToolProvider` to call — `AZURE_FUNCTIONS_BASE_URL` would resolve to an empty string. `inprocess` (`InProcessToolProvider`) keeps every Claims Tool executing inside the API process exactly as it did before the Azure Functions abstraction was introduced. See [ADR-0006](adr/0006-provider-abstraction-pattern.md). |
| `CLAIMS_WORKFLOW_PROVIDER` (`claimsWorkflowProvider` param) | `inprocess` | Same reasoning as above — `InProcessClaimsWorkflowProvider` runs claim registration + adjuster assignment as direct Tool calls rather than starting a Durable Functions orchestration that does not exist in this environment. |
| `llmProvider` | `azure_openai` | The deployed API calls the real Azure OpenAI `gpt-5-mini` deployment, using Entra ID (`DefaultAzureCredential`) authentication by default (no API key configured). |
| `knowledgeProvider` | `local` | Azure AI Search is provisioned (Section 3.2) but no index has been built/populated — selecting `azure_ai_search` here would make `AzureAISearchProvider` fail at startup. The API instead serves RAG content from `configs/knowledge_base/` on disk. |
| `conversationStoreProvider` | `cosmos` | The deployed API persists real conversation history to the live Cosmos DB account. |
| `enablePrivateNetworking` | `false` | Conservative-cost DEV posture — every data-plane resource remains publicly reachable, RBAC-gated only. See [ADR-0001](adr/0001-networking-posture-and-vnet-deferral.md)/[ADR-0002](adr/0002-vnet-private-endpoints-hardening.md). |

Every one of these settings is a **configuration value, not a code path** — flipping any of them
(once its prerequisite exists, e.g. quota for `deployServerlessToolLayer`) requires a Container
App environment-variable/parameter change, never a code redeploy. This is a direct consequence of
the provider-abstraction pattern documented in [ADR-0006](adr/0006-provider-abstraction-pattern.md).

---

## 9. Deployment Validation

Validation performed after every real DEV release, in the order actually implemented by the
pipeline's `SmokeTests` stage plus additional manual validation recorded in sprint evidence.

| Check | Method | Evidence |
|---|---|---|
| Deployed revision/image match | `az containerapp show ... --query "properties.template.containers[0].image"`, compared against the pipeline run's own tag | `azure-pipelines.yml`, `SmokeTests` stage, check 1/4 |
| API liveness | `curl -sf --max-time 30 https://<api-fqdn>/health` → expects `200 {"status":"ok"}` | `azure-pipelines.yml` check 2/4; `docs/sprint_04/validation.md` |
| API readiness (dependency-aware) | `GET /ready` → `200 {"status":"ready", "checks": {...}}` when Cosmos/Azure OpenAI/AI Search (whichever are configured) are reachable, else `503 {"status":"degraded", ...}` | `apps/api/src/api/routes/health.py` (implemented; **not yet wired into the pipeline's own `SmokeTests` stage**, which currently checks `/health` only — see Section 14) |
| Web validation | Manual live validation: correct Spanish UI strings, correct live API FQDN, CORS preflight against the deployed Web origin succeeds | `docs/sprint_08/decisions.md` |
| `POST /chat` — Claims scenario + correlation ID | `curl -X POST https://<api-fqdn>/chat -H "X-Correlation-ID: <id>" -d '{"userId":"...","message":"I need to report a claim for policy SYN-POL-0001."}'` — asserts `agent == "ClaimsAgent"` and the correlation ID is echoed back unchanged | `azure-pipelines.yml` check 3/4 |
| Cross-domain / conversation continuity | A second `POST /chat` reusing the same `conversationId` — asserts the `conversationId` is preserved | `azure-pipelines.yml` check 4/4 |
| Broker scenario | Manually validated during live DEV sessions (not part of the automated pipeline smoke tests today) | `docs/sprint_09/validation.md` (PBI-09-01 controlled release) |
| Commercial scenario | Manually validated during live DEV sessions (not part of the automated pipeline smoke tests today) | `docs/sprint_09/validation.md` |
| Correlation ID propagation end-to-end | `X-Correlation-ID` sent on a request is confirmed echoed back unchanged on the response, both in automated smoke tests and in manual Function-App-era validation (Supervisor → Agent → Tool path) | `azure-pipelines.yml`; `docs/Architecture/adr/0003-azure-functions-tool-and-workflow-layer.md` |
| Monitoring validation | Confirming `errorRateAlert`/`latencyAlert`/`availabilityAlert` (`modules/monitor-alerts.bicep`) exist and reference the correct Application Insights resource/API Container App | `docs/sprint_08/decisions.md` (deployment of the monitoring module) — **no repository evidence of an alert having actually fired and been observed in DEV**; treat monitoring as provisioned and configured, not as end-to-end fire-drill-tested. |

**Pipeline-automated vs. manual**: the four `SmokeTests` stage checks (image match, `/health`,
Claims + correlation ID, continuity) run automatically on every `main` deployment. The Broker and
Commercial scenario validations, `/ready` validation, and monitoring/alert validation were
performed manually during specific sprint releases (cited above) and are **not** part of the
automated pipeline today — see the Deployment Checklist (Section 14) and recommendations at the
end of this report.

---

## 10. Rollback Strategy

No dedicated "rollback" pipeline stage exists in `azure-pipelines.yml`. Rollback in this platform
is a manual, deliberate action built on two properties the deployment design already guarantees:

1. **Every previous image remains pullable.** Because image tags are never `latest` and always
   encode a unique build ID + commit SHA (Section 7.3), any prior release's exact image is still
   present in ACR and can be redeployed by tag.
2. **Container Apps retains prior revisions.** Even under `activeRevisionsMode: 'Single'`, a
   previous revision is not deleted when a new one is activated — it remains present, inactive,
   and immediately available. This was directly observed in a real DEV release: after the Web
   Container App was updated, `docs/sprint_08/decisions.md` records that "the previous revision
   (`ca-tmxap-dev-web--0000004`) was **not** deleted — still present, `active: true`, `0%`
   traffic, immediately available for rollback via `az containerapp ingress traffic set`."

### 10.1 Rollback procedure

**Primary method — redeploy the previous known-good image tag:**

```
az containerapp update \
  --name <api-app-name-or-web-app-name> \
  --resource-group rg-tmx-agent-platform-dev \
  --image <acr-login-server>/<tmx-api-or-tmx-web>:<previous-imageTag>
```

This is the same command the `DeployDev` pipeline stage uses for forward deployment (Section
7.4), pointed at a previous tag instead of the current one. It creates a new revision running the
previous image's exact content — the same `activeRevisionsMode: 'Single'` behavior applies, so
the rolled-back revision immediately receives 100% of traffic once healthy.

**Secondary/observational method — reactivate a still-present prior revision**, when one exists
and has not yet been deprovisioned by Container Apps' own revision garbage collection: identify it
via `az containerapp revision list --name <app> --resource-group rg-tmx-agent-platform-dev`, then
route traffic to it. This is the mechanism directly observed in `docs/sprint_08/decisions.md`;
note that Azure Container Apps' revision-traffic commands (including
`az containerapp ingress traffic set`) are primarily designed for `Multiple` revision mode — since
this platform uses `Single` mode, the **primary method above (redeploy by image tag) is the
reliably supported rollback path**, and the observed prior-revision persistence should be treated
as a secondary confirmation that a rollback target still exists, not as the guaranteed mechanism.

### 10.2 Infrastructure rollback

No rollback procedure for `ops/bicep/main.bicep` changes is implemented or documented in this
repository beyond Bicep's own idempotent-reapply property (re-running `az deployment group
create` with a prior commit's Bicep source restores that prior resource configuration). No
automated Bicep rollback stage exists in the pipeline.

---

## 11. CI/CD Pipeline

Implemented entirely in `azure-pipelines.yml` (Azure DevOps Pipelines), per CLAUDE.md §7.1: once
operational, this pipeline — not manual `az`/`docker` commands — owns build, test, security,
infrastructure deployment, DEV deployment, and smoke testing.

### 11.1 Branch strategy

- `main` — the only branch that triggers deployment stages.
- `feat/*`, `fix/*`, `review/*` — trigger validation-only stages (Quality, Security, Build
  validation, Infrastructure validation); never deploy.
- No long-lived `develop`/integration branch exists (`azure-pipelines.yml` header comment, PBI-07-01B).

### 11.2 Pull Requests

`pr: branches: include: [main]` — every PR targeting `main` runs the full validation path
(Quality, Security, `ContainerBuildValidation`, `InfrastructureValidation`) before merge, with no
deploy-affecting stage.

### 11.3 Continuous Integration (Quality + Security gates)

| Stage | What it runs | Fails the build on |
|---|---|---|
| `BackendQuality` | Full `pytest` suite (`tests/`), `ruff check`, `mypy` | Any test failure, lint violation, or type error |
| `FrontendQuality` | `npm run lint`, `npm run typecheck`, `npm run test` (Vitest), `npm run build` | Any of the above failing |
| `SecurityScan` | `pip-audit` (Python CVEs), `npm audit --omit=dev --audit-level=high` (production JS dependency CVEs, blocking), `npm audit` full report (informational, non-blocking), `detect-secrets scan` (committed-secret scan) | A blocking finding in any of the three blocking checks |

### 11.4 Automated tests

The full `tests/` suite (`unit/`, `integration/`, `conversational/`) runs in `BackendQuality` via
one `pytest tests/` invocation with coverage reporting (`--cov=src --cov=apps/api/src`), published
as a JUnit report and a coverage artifact. Frontend unit tests run via Vitest in `FrontendQuality`.

### 11.5 Bicep validation

Covered in Section 6.3 — `InfrastructureValidation` (offline `az bicep build`, every run) and the
live `az deployment group validate` step inside `InfrastructureDeploy` (deploy runs only).

### 11.6 Continuous Deployment

`ContainerBuildAndPush` → `InfrastructureDeploy` (parallel/independent) → `DeployDev` →
`SmokeTests` → `DeploymentSummary`, all gated to `main` pushes only (`isDeployRun`). `DeployDev`
does **not** depend on `InfrastructureDeploy` succeeding — an infrastructure-only failure (e.g.,
the known Function App quota block) never blocks API/Web image delivery, by construction (not on
the dependency graph at all, not merely error-handled).

### 11.7 Smoke Tests

Covered in Section 9 — the four automated checks in the `SmokeTests` stage.

### 11.8 Known limitation — Azure DevOps Hosted Parallelism

The project's Azure DevOps organization currently does not have a Microsoft-hosted parallelism
grant available for this pipeline to consume, which prevents Microsoft-hosted agent jobs from
running. **This constraint is not evidenced by any file in this repository** — Azure DevOps
pipeline run history and parallelism-grant status live in the Azure DevOps service itself, not in
version-controlled files, so it cannot be independently confirmed by a repository scan; it is
recorded here as a project-team-reported operational fact.

The standard operational workaround for this class of constraint (Microsoft's own documented
options, not a repository-evidenced choice made by this project) is one of:

1. Requesting a free-tier parallelism grant via Microsoft's public grant-request form (Microsoft
   grants these per Azure DevOps organization, subject to eligibility and processing time).
2. Purchasing a paid Microsoft-hosted parallelism tier for the organization.
3. Registering a self-hosted agent (a VM or local machine running the Azure Pipelines agent),
   which does not consume Microsoft-hosted parallelism at all.

This repository's pipeline (`azure-pipelines.yml`) targets `vmImage: ubuntu-latest` (Microsoft-
hosted) in every job — it contains no self-hosted agent pool configuration. Until a parallelism
grant is obtained or a self-hosted agent is registered, pipeline runs as authored in this file
cannot execute; validation described throughout this guide has instead been performed via direct,
manually-invoked `az`/`docker` commands against the real DEV resource group (see the sprint
evidence cited in Sections 6, 7, 9, and 13), which is why every stage's command pattern
documented in this guide has real, cited evidence even though no automated pipeline run is
recorded.

---

## 12. Known Deployment Constraints

Only constraints with direct repository evidence of having actually occurred.

| Constraint | Evidence |
|---|---|
| **`Microsoft.Web` (App Service) quota is zero in this subscription, in every region checked, for every SKU tried.** Blocks the Azure Functions Tool Layer / Durable Functions workflow engine from deploying. 3 independent real `az deployment group create` attempts (`Y1`, `B1`, `P0v4` — twice) all failed identically with `SubscriptionIsOverQuotaForSku`. | [ADR-0003](adr/0003-azure-functions-tool-and-workflow-layer.md); `docs/sprint_06/decisions.md` |
| **Azure Functions Tool Layer is disabled in DEV** as a direct consequence of the above (`deployServerlessToolLayer=false`). Application code and Bicep modules for it exist and are tested; only physical deployment is disabled. | `ops/bicep/parameters/dev.bicepparam`; [ADR-0003](adr/0003-azure-functions-tool-and-workflow-layer.md) |
| **Azure DevOps Hosted Parallelism is currently unavailable** for this pipeline. | Reported by the project team; not independently verifiable from repository files — see Section 11.8. |
| **Synthetic data environment.** No real customer, policy, claim, broker, or commission data exists anywhere in this platform — every Tool operates against synthetic datasets (`src/services/tools/synthetic/`). | CLAUDE.md §1/§2; `src/services/tools/synthetic/provider.py` |
| **Microsoft Entra ID user-facing authentication is intentionally deferred for this academic version.** CLAUDE.md §4.5 specifies it as target architecture; no MSAL/OIDC client exists in `apps/web/`, and no JWT/token validation middleware exists in `apps/api/src/api/`. Every resource-to-resource identity in this platform (Managed Identity, RBAC) is implemented; **end-user login is not.** | `apps/web/package.json` (no auth library present); `apps/api/src/api/` (no auth middleware present); CLAUDE.md §4.5 target vs. Section 3.3 of this guide |
| **Azure AI Search region moved from `eastus2` to `eastus`** during initial deployment due to a real, transient regional capacity shortage (`InsufficientResourcesAvailable`, encountered twice). | `docs/sprint_03/decisions.md` |
| **Azure OpenAI model changed from `gpt-4o-mini` to `gpt-5-mini`** during initial deployment: `gpt-4o-mini:2024-07-18` was rejected as `"Deprecating"`/`ServiceModelDeprecating` for new deployments in the live model catalog. | `docs/sprint_03/decisions.md` |
| **VNet/Private Endpoints are deferred in DEV** (`enablePrivateNetworking=false`) — a deliberate, documented, conservative-cost posture for a synthetic-data academic environment, not an oversight. | [ADR-0001](adr/0001-networking-posture-and-vnet-deferral.md); [ADR-0002](adr/0002-vnet-private-endpoints-hardening.md) |

---

## 13. Troubleshooting

Only issues with direct repository evidence of having actually been encountered.

| Problem | Possible Cause | Resolution |
|---|---|---|
| `az deployment group create` fails with `SubscriptionIsOverQuotaForSku` on `Microsoft.Web/serverFarms` | This subscription has zero App Service quota for any SKU, in every checked region (confirmed via `Microsoft.Web/locations/{region}/usages`) | This is a genuine, external Azure subscription limitation — no SKU choice or retry resolves it. Set/keep `deployServerlessToolLayer=false` in the relevant `.bicepparam` file; every other resource in `main.bicep` still deploys. Requires an Azure Support quota-increase request to actually resolve. See [ADR-0003](adr/0003-azure-functions-tool-and-workflow-layer.md). |
| New Azure AI Search service creation fails with `InsufficientResourcesAvailable` | Transient regional capacity shortage in the target region (`eastus2` at the time) | Add/override `aiSearchLocation` to a region with available capacity (`eastus` was confirmed to work) via the relevant `.bicepparam` file; no code change required. |
| Azure OpenAI deployment fails with `ServiceModelDeprecating` | The requested model version (`gpt-4o-mini:2024-07-18`) has lifecycle status `Deprecating` in the live Azure OpenAI model catalog and is rejected for new deployments | Select a currently `GenerallyAvailable` model in the same tier (`gpt-5-mini:2025-08-07` was the confirmed successor at the time) via `azureOpenAiModelName`/`azureOpenAiModelVersion` in the relevant `.bicepparam` file. |
| `az acr build` appears to fail locally with a `UnicodeEncodeError` (`colorama`/Windows-console log-streaming crash) | A cosmetic Azure CLI console-encoding bug on Windows when streaming remote ACR build logs — the remote build itself is unaffected | Do not treat the local CLI crash as a build failure. Confirm the real outcome with `az acr task list-runs --top 1 --query "[0].status"` and `az acr repository show-tags` — the remote build frequently still succeeds and pushes the image. |
| `docker build`/local Docker unavailable during a deployment session | Local Docker daemon not running/available in the working environment | Use `az acr build --registry <acr-name> --image <name>:<tag> --file <dockerfile> <context>` as a remote-build fallback — builds inside ACR itself, no local Docker daemon required. |
| A generic (`UNKNOWN`-intent) `POST /chat` smoke-test message returns `FallbackAgent` instead of a domain agent | Expected behavior, not a defect — `RuleBasedIntentResolver` correctly classifies a message with no domain keyword match as `UNKNOWN` | No action required; confirm the smoke-test message intentionally targets a specific domain (e.g., mentions a policy/claim) if a domain-agent response is expected. See [ADR-0007](adr/0007-ai-governance-boundary.md). |
| `apps/api/Dockerfile`-built image fails to import `AzureOpenAIProvider`/`CosmosConversationRepository` at container startup | The relevant Azure SDK package (`openai`, `azure-identity`, `azure-cosmos`) was not installed in the image, even though `llmProvider=azure_openai`/`conversationStoreProvider=cosmos` were selected at the infrastructure level | Ensure `apps/api/Dockerfile`'s `pip install` list includes every SDK package required by the providers actually selected in the target environment's runtime configuration (Section 8). |

---

## 14. Deployment Checklist

A checklist an engineer can follow before releasing a new version to DEV, reflecting the process
actually implemented in this repository. Items marked **(manual)** are not currently automated by
`azure-pipelines.yml` and must be performed by hand, per the sprint evidence cited above.

- [ ] Confirm the target branch is `main` and the change has passed PR review.
- [ ] Confirm `BackendQuality` and `FrontendQuality` (pytest/ruff/mypy; lint/typecheck/test/build)
      pass locally or in the pipeline before merge.
- [ ] Confirm `SecurityScan` (pip-audit, npm audit production deps, detect-secrets) has no new
      blocking findings.
- [ ] Confirm `InfrastructureValidation` (`az bicep build` for every module + parameter file)
      passes for any Bicep change in this release.
- [ ] If infrastructure changed: run `az deployment group validate` against
      `rg-tmx-agent-platform-dev` before `az deployment group create` (Section 6.4).
- [ ] Confirm the image tag being deployed is not `latest` and encodes a real build ID + commit
      SHA (Section 7.3).
- [ ] Deploy via `az containerapp update` (API always; Web only if `apps/web/` changed) — never a
      Bicep redeploy for an application-only release (Section 7.4).
- [ ] Run the four automated smoke tests (image/revision match, `/health`, Claims + correlation
      ID, continuity) — Section 9.
- [ ] **(manual)** Validate `GET /ready` reports `"status": "ready"` with every configured
      dependency `"ok"`.
- [ ] **(manual)** Validate a Broker Services scenario end-to-end.
- [ ] **(manual)** Validate a Commercial Intake scenario end-to-end.
- [ ] **(manual)** Validate a cross-domain conversation (e.g., Claims → Broker → Claims) preserves
      state correctly — see [ADR-0009](adr/0009-conversation-memory-strategy.md).
- [ ] **(manual)** Confirm the Web frontend loads, displays correctly, and successfully calls the
      just-deployed API (CORS, correct FQDN).
- [ ] Confirm the previous image tag/revision is known and recorded, in case rollback (Section 10)
      is needed.
- [ ] Update the relevant `docs/sprint_NN/` evidence and `validation.md` with the commands
      actually run and their results (CLAUDE.md §12/§13).

---

## Cross-references

- [ADR-0001](adr/0001-networking-posture-and-vnet-deferral.md) — Networking posture
- [ADR-0002](adr/0002-vnet-private-endpoints-hardening.md) — VNet/Private Endpoints hardening
- [ADR-0003](adr/0003-azure-functions-tool-and-workflow-layer.md) — Azure Functions Tool Layer
- [ADR-0004](adr/0004-conversation-store-selection.md) — Conversation store selection
- [ADR-0005](adr/0005-application-hosting-strategy.md) — Application hosting strategy
- [ADR-0006](adr/0006-provider-abstraction-pattern.md) — Provider abstraction pattern
- [ADR-0007](adr/0007-ai-governance-boundary.md) — AI governance boundary
- [ADR-0008](adr/0008-resilience-strategy.md) — Resilience strategy
- [ADR-0009](adr/0009-conversation-memory-strategy.md) — Conversation memory strategy

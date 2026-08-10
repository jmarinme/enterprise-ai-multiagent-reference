# Azure DevOps — One-Time Setup for the First Real Pipeline Run

Updated PBI-07-01A (2026-08-10) to reflect the real Azure DevOps configuration, created manually
and confirmed live via `az ad sp show`/`az ad app federated-credential list`/`az role assignment
list` — not assumed. Nothing below invents or guesses a credential.

## Status — what already exists

| Item | Status |
|---|---|
| Azure subscription, resource group (`rg-tmx-agent-platform-dev`) | Exists, operational |
| Azure DevOps organization (`tokio-marine-mx-devops`) + project (`Enterprise-ai-multiagent-reference`) | **Done** |
| Azure DevOps service connection (`sc-tmx-agent-platform-dev`), ARM, Workload Identity Federation, "App registration (automatic)" | **Done** |
| — backing identity | Azure-DevOps-managed App Registration/service principal — appId `e35d2b19-6ac8-41e5-af14-66a9095d4e35`, object id `9f6190e9-b5dd-4651-a90b-45d9f37bcc5a`. **Not** `id-tmxap-dev` — confirmed via `az ad app federated-credential list`, which shows a federated credential literally named "Federation for Service Connection sc-tmx-agent-platform-dev in https://dev.azure.com/tokio-marine-mx-devops/Enterprise-ai-multiagent-reference/..." |
| — scope | Subscription Pay-As-You-Go, resource group `rg-tmx-agent-platform-dev` |
| — RBAC currently held | **`Contributor`, scoped to `rg-tmx-agent-platform-dev`** — confirmed via `az role assignment list --resource-group rg-tmx-agent-platform-dev`. Granted automatically by Azure DevOps's own "automatic" WIF flow at connection-creation time — **not** by this repo's Bicep (a real grant that exists in Azure, not yet codified as IaC — see `decisions.md`). |
| Repository connected to the Azure DevOps project (GitHub connection / Azure Repos import) | **Not yet done** |
| Pipeline created from `azure-pipelines.yml` | **Not yet done** |
| Pipeline authorized to use `sc-tmx-agent-platform-dev` | **Not yet done** (can't be, until the pipeline exists) |
| `id-tmxap-dev`'s `AcrPush`/`Container Apps Contributor` grants (PBI-04-01) | Still applied to real Azure, but **not used by the real pipeline identity** — that identity is different (see above). Harmless, not cleaned up here (a separate, not-yet-authorized decision). |
| `ops/bicep/main.bicep`'s `cicdInfrastructureContributorPrincipalId` param | Off (empty string) — **not needed**: the real service connection principal already has Contributor (see above). Exists only as an optional future path to bring that already-existing grant under IaC control. |

## Corrected identity model (PBI-07-01A)

PBI-07-01's original design assumed the Azure DevOps service connection would be configured to
target the platform's existing user-assigned Managed Identity, `id-tmxap-dev` (per
`docs/sprint_00/security-baseline.md` §6's original recommendation). **This did not happen** —
whoever created the service connection used Azure DevOps's "App registration (automatic)" path,
which creates and manages its own, brand-new Entra ID App Registration rather than targeting an
existing identity. This is a completely valid, equally-secure Workload Identity Federation
configuration (still no stored secret, still OIDC token exchange) — just a different principal
than originally planned. Every RBAC decision in this repository must now reference the **real**
principal (`9f6190e9-b5dd-4651-a90b-45d9f37bcc5a`), not `id-tmxap-dev`, for anything related to
the Azure DevOps pipeline specifically. `id-tmxap-dev` remains the platform's own **runtime**
identity (used by the API/Web Container Apps themselves to reach Cosmos DB, Key Vault, Azure
OpenAI, AI Search, and to pull images from ACR at runtime) — that role is unchanged and
unaffected by any of this.

## Remaining steps

### Step 1 — Connect the repository (GitHub connection / Azure Repos import)

If this repository is hosted on GitHub: **Project Settings → GitHub connections** (or grant
access via the Azure Pipelines GitHub App when creating the pipeline in Step 2) so Azure
Pipelines can read the repo and receive push/PR webhooks. If it should live in Azure Repos
instead, import it there. Neither path requires a stored credential beyond the standard
GitHub App/OAuth authorization flow.

### Step 2 — Create the pipeline

**Pipelines → New pipeline → (select the connected repo) → Existing Azure Pipelines YAML file →
`/azure-pipelines.yml`.** Save (or "Save and run" to trigger immediately).

### Step 3 — Authorize the pipeline to use the service connection

The first time a pipeline run actually attempts to use `sc-tmx-agent-platform-dev`, Azure
Pipelines shows a one-time "This pipeline needs permission to access a resource" prompt — click
**Permit**. (Service connections can also be pre-authorized for all pipelines in
**Project Settings → Service connections → sc-tmx-agent-platform-dev → Security → Pipeline
permissions**, if you'd rather not wait for the first-run prompt.)

### Step 4 — First run

Trigger a run against a `feat/*`/`fix/*`/`review/*` branch, or a PR against `main`, first — this
project has no `develop` branch (PBI-07-01B corrected this pipeline's branch strategy to match
the real Git workflow: `main`, `feat/*`, `fix/*`, `review/*`, no long-lived integration branch —
see CLAUDE.md §15). Validates Quality/Security/`ContainerBuildValidation` (a real, no-push
`docker build` check)/Infrastructure-Validate only, deploys nothing, no service-connection
authentication needed at all (Bicep `build`/`build-params` and `docker build` are all pure
offline checks). Once that's confirmed green, push to `main` (or merge a PR into it) to exercise
the full deploy path.

### Step 5 (conditional) — Any RBAC adjustment proven necessary

Per the Status table above, **no RBAC change should be necessary** — the real service connection
principal already holds `Contributor` on `rg-tmx-agent-platform-dev`, which covers ACR push,
Container App updates, and Bicep resource deployment (everything except role-assignment writes).
This has **not** been empirically confirmed against a live OIDC token exchange through this exact
service connection (every `az` check so far used the human user's own Owner-level session to
inspect Azure state, not the pipeline's own identity actually authenticating). If the first real
run's `ContainerBuildAndPush`, `InfrastructureDeploy`, or `DeployDev` stage fails with an
authorization error despite the above, that is the signal to revisit this — see "If something
doesn't match this document" below. Do not preemptively grant anything further.

## What to expect on the first `main` deploy run

- `BackendQuality`/`FrontendQuality`/`SecurityScan`/`InfrastructureValidation` — should pass
  exactly as validated locally in `docs/sprint_07/validation.md`.
- `ContainerBuildAndPush` — first real test of `az acr login`/`docker push` using
  `sc-tmx-agent-platform-dev`. Should succeed — `Contributor` on the resource group covers ACR
  push actions.
- `InfrastructureDeploy` — should succeed for every resource **except** the Claims Tool Layer
  Function App, which will report the known, non-blocking `partial-quota-blocked` condition
  (Azure subscription App Service quota is still `0` — see
  `docs/Architecture/adr/0003-azure-functions-tool-and-workflow-layer.md`) — unrelated to this
  PBI's identity-reconciliation work. The `Microsoft.Authorization/roleAssignments` resources
  already declared in `main.bicep` (the pre-existing `id-tmxap-dev` role grants) may also report
  an authorization error on every run, since `Contributor` excludes
  `Microsoft.Authorization/*/write` — expected and, per the design in
  `docs/sprint_07/decisions.md`, does not fail the stage unless it's the *only* failure and
  doesn't match the quota signature (in which case investigate — this specific
  roleAssignment-authorization case was anticipated but not given its own special-cased
  exit-0 handling in the pipeline script; see `decisions.md`'s PBI-07-01A entry).
- `DeployDev`/`SmokeTests` — should succeed regardless of `InfrastructureDeploy`'s outcome — the
  behavior this whole design exists to guarantee. If either fails, that's a real problem
  unrelated to infrastructure/quota — investigate independently.
- `DeploymentSummary` — publishes a `deployment-summary` artifact regardless of
  `InfrastructureDeploy`'s specific outcome.

## If something doesn't match this document

No real pipeline run has occurred yet in any session — everything about the service connection's
actual behavior (RBAC sufficiency, whether `InfrastructureDeploy`'s roleAssignment-authorization
edge case actually occurs and with what exact error text) is inferred from `az` calls made with
the human user's own credentials, not a live OIDC token exchange through
`sc-tmx-agent-platform-dev` itself. Treat this document and `decisions.md` as the hypothesis to
update, not as ground truth, once a real run happens — record the actual observed behavior as a
new dated entry in `docs/sprint_07/decisions.md`.

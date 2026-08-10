# Sprint 07 — Enterprise CI/CD Pipeline

## Objective

Move deployment/validation responsibility from Claude Code to Azure DevOps Pipelines. Extend
the existing `azure-pipelines.yml` (built in PBI-00-07, extended in PBI-04-01) so that Azure
DevOps — not Claude Code — owns full regression, security gates, image build/push,
infrastructure validation/deployment, DEV deployment, smoke tests, and deployment evidence.
Claude Code's role narrows to implementation, targeted local validation, and documentation; it
stops before deployment once this pipeline is operational.

## Scope

- [x] PBI-07-01: Enterprise CI/CD Pipeline (Quality, Security, Build, Infrastructure, Deploy
      DEV, Smoke Tests stages; Azure DevOps Workload Identity Federation prerequisites
      documented; CLAUDE.md delivery-responsibility model updated).
- [x] PBI-07-01A: Reconcile the pipeline with the Azure DevOps project/service connection
      actually created manually — corrected service connection name and identity-model
      assumption, confirmed the real RBAC state live, updated setup documentation.
- [x] PBI-07-01B: Correct the trigger/PR branch strategy to this project's real Git workflow
      (`main`/`feat/*`/`fix/*`/`review/*`, no `develop`); add a build-only validation stage for
      feature branches with zero Azure exposure; verify every deploy stage is explicitly
      main-branch-gated.

## Out of scope

- Creating the actual Azure DevOps organization/project/service connection, or triggering a
  real pipeline run — no Azure DevOps org/PAT is available in this or any prior session (same
  documented limitation as PBI-04-01). Fully documented as a one-time manual prerequisite in
  `azure-pipelines.yml`'s own header and `azure-devops-setup.md`.
- Applying the new `cicdInfrastructureContributorPrincipalId` RBAC grant to the real DEV
  environment — Bicep support is additive and off by default (empty string skips the role
  assignment); applying it requires its own explicit human approval, per the same pattern
  PBI-04-01 already established for its own RBAC additions (see `decisions.md`).
- A live, real `az deployment group create` exercise of the new `InfrastructureDeploy` stage's
  script logic against Azure — validated via local script/condition/variable-flow review and
  Bicep compilation only, consistent with this PBI's own "targeted local validation only, do
  NOT manually repeat the complete deployment flow the pipeline is supposed to own" instruction.
- A real Docker/npm/pip-audit run *inside an actual Azure Pipelines agent* — the security-tool
  findings and gate design were validated locally (isolated Python venv matching the pipeline's
  exact dependency-install list; local `npm audit`) against the real, current state of this
  repository's dependencies, not fabricated.
- Any change to Agent, Supervisor, PromptManager, Tool Calling, RAG, or business-logic code.
- A QA/Production Azure DevOps environment, approval gates, or additional Azure DevOps
  "Environment" resources.
- Redesigning any existing Azure infrastructure — every Bicep change this PBI made is additive
  (one new opt-in parameter + role assignment); no existing resource module was altered.

## Deliverables

- [x] PBI-07-01: `SecurityScan` stage (pip-audit, npm audit, detect-secrets); `InfrastructureDeploy`
      stage (quota-aware, non-blocking for API/Web delivery); Web-only-when-changed build/deploy
      logic; commit-SHA image tag traceability; expanded `SmokeTests` (correlation ID,
      conversation continuity, a Claims scenario, deployed-revision verification); new opt-in
      `cicdInfrastructureContributorPrincipalId` Bicep RBAC parameter; CLAUDE.md §7.1 delivery
      responsibility model; `docs/sprint_07/azure-devops-setup.md` one-time setup guide.
- [x] PBI-07-01A: `azureServiceConnection` default corrected to `sc-tmx-agent-platform-dev`;
      identity model corrected with live evidence (the real service connection principal is an
      Azure-DevOps-managed App Registration, object id `9f6190e9-b5dd-4651-a90b-45d9f37bcc5a`,
      not `id-tmxap-dev`); confirmed that principal already holds `Contributor` on
      `rg-tmx-agent-platform-dev` (auto-granted by Azure DevOps, not this repo's Bicep) — no new
      RBAC change made; `azure-devops-setup.md` rewritten to reflect the real, current state.

## Acceptance criteria

| ID | Criterion | Evidence |
|---|---|---|
| AC-01 | Existing YAML pipeline reused and improved — no Classic pipeline created | `azure-pipelines.yml` — single file, `stages:`-based, extends PBI-00-07/PBI-04-01's file in place |
| AC-02 | Stage 1 (Quality): Python/frontend dependency caching, ruff, mypy, pytest, frontend tests/typecheck/lint/build | `BackendQuality`/`FrontendQuality` stages — unchanged from PBI-04-01, confirmed still present |
| AC-03 | Stage 2 (Security): Python dependency scan, npm audit, secret scan; no heavyweight product | New `SecurityScan` stage — `pip-audit`, `npm audit --omit=dev`, `detect-secrets`, all lightweight/pip-or-npm-installable |
| AC-04 | Stage 3 (Build): API image always; Web image only when relevant; versioned push to existing ACR; commit/build traceability | `ContainerBuildAndPush` — `detectWebChange` step + conditional Web build/push; `imageTag` now includes `$(Build.SourceVersion)` |
| AC-05 | Stage 4 (Infrastructure): Bicep build/validate; deploy only required DEV changes; quota blocker must not fail unrelated API/Web delivery, documented | `InfrastructureValidation` (unchanged, offline) + new `InfrastructureDeploy` (quota-aware exit-0 handling, structurally independent of `DeployDev`/`SmokeTests`) |
| AC-06 | Stage 5 (Deploy DEV): update API Container App; update Web only when changed; no shared-resource recreation | `DeployDev` — `az containerapp update --image` only; Web update now conditioned on `webChanged` |
| AC-07 | Stage 6 (Smoke Tests): /health, real POST /chat, conversation continuity, a Claims scenario, correlation ID, deployed revision/tag | `SmokeTests` — 4 steps covering all 6 checks (revision/tag; /health; Claims scenario + correlation ID; continuity) |
| AC-08 | Service connection: Workload Identity Federation, no stored secret; setup steps documented if not yet created | `azure-pipelines.yml` header PREREQUISITES; `azure-devops-setup.md` |
| AC-09 | CLAUDE.md delivery-responsibility model updated | CLAUDE.md §7.1 |
| AC-10 | Sprint 07 docs created | This file, `implementation-plan.md`, `decisions.md`, `validation.md`, `azure-devops-setup.md` |
| AC-11 | Targeted local validation only; no manual repeat of the full deployment flow | `validation.md` — YAML syntax, Bicep compilation, local isolated-venv `pip-audit`/`npm audit`/`detect-secrets` runs; no `az deployment group create`/`az containerapp update` executed this PBI |

## Dependencies

- PBI-00-07's CI foundation and PBI-04-01's Continuous Deployment stages — this PBI extends,
  not replaces, that file (`docs/sprint_04/decisions.md`'s "extended the existing
  `azure-pipelines.yml` in place" precedent, followed again here).
- PBI-04-01's Workload Identity Federation service connection design and its two RBAC role
  assignments (AcrPush; Container Apps Contributor) — still the prerequisite for
  `ContainerBuildAndPush`/`DeployDev`/`SmokeTests`; APPLIED to the real DEV environment already.
- `reports/review/02_security_review.md` Finding SEC-08 — the review this PBI's Security stage
  resolves.
- Sprint 06/06-01A's Azure subscription App Service quota finding
  (`docs/Architecture/adr/0003-azure-functions-tool-and-workflow-layer.md`,
  `docs/sprint_06/decisions.md` D-07) — the exact, empirically-confirmed error signature the new
  `InfrastructureDeploy` stage's non-blocking handling is built against.

## Risks

| Risk | Probability | Impact | Mitigation |
|---|---:|---:|---|
| No Azure DevOps organization/PAT available to create the service connection, the new Contributor RBAC grant, or trigger a real pipeline run | Realized (same as PBI-04-01) | Medium | Fully documented one-time prerequisite (`azure-devops-setup.md`); every script's logic validated locally instead |
| `InfrastructureDeploy`'s quota-aware error handling has not been exercised against a real pipeline run (only against 3 real `az deployment group create` attempts from a user session, not the pipeline's own service-connection identity) | Accepted | Medium | Error-matching string (`SubscriptionIsOverQuotaForSku` + `Microsoft.Web/serverFarms`) is copied verbatim from 3 real, empirically-confirmed Azure error responses (`docs/sprint_06/decisions.md` D-07); any other failure mode fails loudly, not silently |
| The new `Contributor`-scoped-to-RG RBAC grant is broader than any other role this platform's CI identity holds | Accepted, flagged | Medium | Deliberately `Contributor`, not `Owner` (excludes `Microsoft.Authorization/*/write`); off by default (empty-string param); requires its own explicit human approval before being applied — see `decisions.md` |
| `pip-audit`/`npm audit` gates could become permanently red on unrelated future CVEs | Possible | Low | Both gates validated clean against real, current findings as of 2026-08-10 with documented, justified exceptions (`--ignore-vuln PYSEC-2026-1845` for a pytest-only, test-time-only CVE; `--omit=dev` scoping npm audit to the actually-shipped `react`/`react-dom` dependencies) — see `decisions.md` |
| Web-only-when-changed's `git diff HEAD^ HEAD` only compares against the immediate parent commit | Accepted | Low | Correct for this project's single-merge-commit-per-PR flow; documented limitation in `azure-pipelines.yml`'s own comment; defaults to "changed" (always build) when `HEAD^` cannot be resolved |

## Deliverable Log

<!-- Append entries. Do not remove previous entries. -->

PBI-07-01: Extended `azure-pipelines.yml` in place (not a new file) with a `SecurityScan` stage
(`pip-audit`, `npm audit --omit=dev` as the hard gate + full `npm audit` as an informational,
non-blocking report, `detect-secrets` with inline `pragma: allowlist secret` suppressions for 5
confirmed false positives) and a new `InfrastructureDeploy` stage (`az deployment group
validate` + `create` against the real DEV resource group, structurally independent of
`DeployDev`/`SmokeTests`, with quota-aware non-blocking error handling for the
empirically-confirmed `SubscriptionIsOverQuotaForSku`/`Microsoft.Web/serverFarms` condition from
Sprint 06/06-01A). Added Web-only-when-changed build/push/deploy logic
(`git diff HEAD^ HEAD -- apps/web`) and commit-SHA image-tag traceability
(`dev-$(Build.BuildId)-$(Build.SourceVersion)`). Expanded `SmokeTests` from 2 to 4 steps covering
6 checks (deployed revision/tag verification, `/health`, a real Claims scenario with correlation
ID propagation, and conversation continuity). `ops/bicep/main.bicep` gained one new, opt-in,
off-by-default parameter (`cicdInfrastructureContributorPrincipalId`) granting `Contributor`
(never `Owner`) scoped to the resource group only, required solely by the new
`InfrastructureDeploy` stage. `CLAUDE.md` gained §7.1, the Claude-Code-vs-Azure-DevOps delivery
responsibility model. Five pre-existing files gained inline `# pragma: allowlist secret`
comments (all confirmed false positives — parameter/variable NAMES, never values). No Agent,
Supervisor, Tool, RAG, or business-logic code touched. Validated via YAML syntax parsing, real
`az bicep build`/`build-params` compilation, and real local tool runs (an isolated Python venv
matching the pipeline's exact dependency list for `pip-audit`; real `npm audit` against
`apps/web`; real `detect-secrets scan` against the repository) — no live Azure mutation, no
`az containerapp update`, no real pipeline run (no Azure DevOps org/PAT available, same
documented limitation as PBI-04-01). — 2026-08-10
Evidence: `validation.md`, `decisions.md`, `evidence/pbi-07-01-security-tooling-validation.txt`.

PBI-07-01A: Reconciled the pipeline with the Azure DevOps project actually created manually
(org `tokio-marine-mx-devops`, project `Enterprise-ai-multiagent-reference`, service connection
`sc-tmx-agent-platform-dev`). Corrected `azure-pipelines.yml`'s `azureServiceConnection` default
from the assumed `tmx-agent-platform-dev-oidc` to the real name, and rewrote the file's header
"IDENTITY MODEL" block with live-verified facts: the service connection is backed by an
Azure-DevOps-managed App Registration/service principal (appId
`e35d2b19-6ac8-41e5-af14-66a9095d4e35`, object id `9f6190e9-b5dd-4651-a90b-45d9f37bcc5a`,
confirmed via `az ad app federated-credential list` matching a federated credential literally
named for this service connection) — **not** `id-tmxap-dev`, correcting PBI-07-01's original
assumption. Confirmed via `az role assignment list` that this real principal already holds
`Contributor` on `rg-tmx-agent-platform-dev`, auto-granted by Azure DevOps's own service
connection creation flow, outside this repo's Bicep — meaning no new RBAC change is needed for
any pipeline stage to function. Per explicit instruction, **no RBAC change was made**:
`ops/bicep/main.bicep`'s `cicdInfrastructureContributorPrincipalId` param description was
corrected to reference the real principal (for optional future IaC codification) without being
set, and `id-tmxap-dev` was not touched — its PBI-04-01 `AcrPush`/`Container Apps Contributor`
grants remain in place but are now known to be unused by the actual CI/CD pipeline (flagged as
technical debt, not cleaned up). `docs/sprint_07/azure-devops-setup.md` fully rewritten to
reflect what's actually done (org/project/service connection/WIF) versus what remains (GitHub
connection, pipeline creation, pipeline authorization, first real run, any RBAC adjustment the
first run proves necessary). All Quality/Security/Build/Infrastructure/Deploy/SmokeTest stages
preserved unchanged in structure. No deployment, no commit, no push. — 2026-08-10
Evidence: `decisions.md`'s PBI-07-01A entries (live `az` command output quoted verbatim).

PBI-07-01B: Corrected `azure-pipelines.yml`'s branch strategy to this project's real Git
workflow — `trigger.branches.include` changed from `[develop, main]` to
`[main, feat/*, fix/*, review/*]`; `pr.branches.include` changed from `[develop, main]` to
`[main]` only; `docs/**`/`**/*.md` path exclusion preserved unchanged. Added a new
`ContainerBuildValidation` stage (real `docker build` for the API image always, the Web image
only when `apps/web` changed — no `az acr login`, no `docker push`, no service-connection
reference at all) that runs exactly when `ContainerBuildAndPush` does not
(`ne(variables.isDeployRun, true)`), so `feat/*`/`fix/*`/`review/*` pushes and PRs get a real
"does this image build" check without any Azure exposure, and `main` never redundantly builds
twice. Re-verified (via a script printing every stage's `dependsOn`/`condition`) that
`InfrastructureDeploy`/`ContainerBuildAndPush`/`DeployDev`/`SmokeTests`/`DeploymentSummary` each
carry their own explicit `eq(variables.isDeployRun, true)` (or equivalent) condition, not merely
an inherited one — confirming no deployment stage is reachable from a feature branch, directly
or indirectly. Removed every `develop`-branch reference from active pipeline behavior and
updated the three affected `docs/sprint_07/*.md` files (`decisions.md`, `azure-devops-setup.md`)
accordingly. All existing Quality/Security/Build/Infrastructure/Deploy/SmokeTest stage structure
preserved. No deployment, no commit, no push. — 2026-08-10
Evidence: `decisions.md`'s PBI-07-01B entries; live `yaml.safe_load` output showing the full
trigger/pr/stage-condition graph.

## Sprint validation

See `validation.md`.

## Sprint retrospective

Complete when closing the sprint:

- What worked:
- What did not:
- Technical debt:
- Security findings:
- Follow-up PBIs:

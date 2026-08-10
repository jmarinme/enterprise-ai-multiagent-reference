# Sprint 07 — Implementation Plan

## PBI-07-01: Enterprise CI/CD Pipeline

### Step 1 — Inspect the existing pipeline and prior CI/CD PBI work

Read `azure-pipelines.yml` in full (650 lines, 8 stages: `BackendQuality`, `FrontendQuality`,
`InfrastructureValidation`, `ContainerBuildAndPush`, `DeployDev`, `SmokeTests`,
`DeploymentSummary`, `ArtifactPublication`) and `docs/sprint_04/{README,decisions,validation}.md`
(PBI-04-01, the pipeline's own prior real-CI/CD PBI) before changing anything. Confirmed: the
pipeline already implements everything PBI-07-01's Stage 1 (Quality) requires unchanged; Stages
3/5/6 (Build, Deploy DEV, Smoke Tests) exist but needed extension, not creation; Stage 2
(Security) and part of Stage 4 (Infrastructure — the "deploy" half) did not exist at all.

### Step 2 — Security stage design and validation

Rather than guessing at gate thresholds, ran all three candidate tools (`pip-audit`, `npm
audit`, `detect-secrets`) locally against this repository's real, current state first, to design
a gate that is meaningful (catches real issues) without being permanently red (dev-tooling-only
or out-of-scope-major-version findings would train reviewers to ignore it). See
`decisions.md`/`validation.md` for the full evidence and resulting design: `pip-audit` with a
`setuptools` upgrade + one documented `--ignore-vuln`; `npm audit --omit=dev` as the hard gate,
full audit as an informational report; `detect-secrets` with inline pragma suppressions for 5
confirmed false positives plus a path exclusion for frozen historical evidence logs.

### Step 3 — Infrastructure deploy design (the hardest design decision this PBI made)

The existing pipeline deliberately never ran `az deployment group create` (PBI-04-01's own
documented decision — RBAC changes were always human-approval-gated). This PBI's explicit
requirement ("deploy only required DEV infrastructure changes... the pipeline must be READY to
deploy [Functions/Durable] when quota is enabled, but this external blocker must not incorrectly
mark unrelated API/Web delivery as failed") requires the pipeline to actually attempt real
infrastructure deployment. Three sub-decisions, each recorded in `decisions.md`:

1. What RBAC does the CI identity need to run `az deployment group create` against the full
   template? — `Contributor` scoped to the resource group (not `Owner`, not subscription-wide),
   added as a new opt-in, off-by-default Bicep parameter.
2. How does the pipeline avoid letting the known Function App quota block fail the whole run? —
   Structural independence (`DeployDev` never `dependsOn`s `InfrastructureDeploy`) plus a
   narrow, evidence-backed error-string match that treats exactly that one condition as
   non-blocking.
3. What exact error signature to match? — Copied verbatim from 3 real `az deployment group
   create` failures produced in the prior PBI-06-01/06-01A session, not guessed.

### Step 4 — Web-only-when-changed and image tag traceability

Added a `git diff HEAD^ HEAD -- apps/web` detection step (requires `fetchDepth: 2`), threaded
through both `ContainerBuildAndPush` (skip Web build/push) and `DeployDev` (skip Web
`az containerapp update`) via the same cross-stage output-variable pattern the file already used
for `apiFqdn`/`acrLoginServer`. Changed `imageTag` to append `$(Build.SourceVersion)` (full
commit SHA) for direct commit traceability.

### Step 5 — Expanded smoke tests

Rewrote the 2-step `SmokeTests` stage into 4 steps covering 6 checks: deployed revision/image
tag verification (new `AzureCLI@2` step comparing the live Container App's image against this
run's expected tag), `GET /health` (unchanged), a real `POST /chat` Claims scenario
(`SYN-POL-0001`, asserting `agent == "ClaimsAgent"`) with `X-Correlation-ID` round-trip
verification, and a second `POST /chat` reusing the same `conversationId` (continuity).

### Step 6 — CLAUDE.md delivery-responsibility model

Added §7.1 to CLAUDE.md, splitting Claude Code's responsibilities (implement, targeted local
tests, docs, stop before deployment) from Azure DevOps's (full regression, security gates,
builds, ACR push, Bicep validation/deployment, DEV deployment, smoke tests, evidence) — see
`decisions.md` for the exact wording rationale.

### Step 7 — Documentation and validation

`docs/sprint_07/{README,implementation-plan,decisions,validation}.md` plus a dedicated
`azure-devops-setup.md` (this PBI's explicit requirement #6). Validation scoped to what this
PBI's own instructions asked for: YAML syntax, Bicep compilation, script/condition/variable-flow
review, and real local tool runs for the security tooling — no live Azure mutation, no repeat of
the full deployment flow the pipeline itself is meant to own.

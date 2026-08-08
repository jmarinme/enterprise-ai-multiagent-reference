# Sprint 04 Implementation Plan

## PBI-04-01: Azure DevOps CI/CD Pipeline for the TMX Agent Platform DEV Environment

### Pre-work

1. Read `CLAUDE.md`, `docs/sprint_03/*`, `docs/Architecture/*`, `ops/bicep/*`, the existing
   `azure-pipelines.yml` (PBI-00-07), and query the real, live DEV environment (`az resource
   list`, `az containerapp show`, `az acr list`) to confirm current state before changing
   anything.
2. Identify what already exists vs. what is genuinely missing — this PBI extends, not
   replaces, the Sprint-0 CI foundation.

### Findings from pre-work

- A working `azure-pipelines.yml` already exists (Stages 1-5: BackendQuality, FrontendQuality,
  InfrastructureValidation, ContainerBuildValidation, ArtifactPublication), plus a documented
  but `condition: false`-disabled `Deploy_Dev` stage describing the intended future CD flow.
- Two real, pre-existing defects found in that file:
  1. `ContainerBuildValidation` built the API image with `./apps/api` as the Docker build
     context — `apps/api/Dockerfile` has required the repo root as its context since
     PBI-03-02 (it `COPY`s the shared `src/` tree from outside `apps/api`); this command could
     never have produced a working image.
  2. `InfrastructureValidation`'s `bicepModuleFiles` parameter list only had 10 of the 14
     modules under `ops/bicep/modules/` — `ai-search.bicep`, `azure-openai.bicep`,
     `private-dns-zone.bicep`, `private-endpoint.bicep`, and `virtual-network.bicep` (all added
     by PBI-02-02/PBI-03-02/PBI-03-04) were never being validated.
- The Managed Identity currently has zero control-plane RBAC (only data-plane roles: Cognitive
  Services OpenAI User, Search Index Data Reader, Cosmos DB Data Contributor, Key Vault
  Secrets User, AcrPull) — it cannot push images or update Container Apps yet.
- `docs/sprint_00/security-baseline.md` §6 already recommends Workload Identity Federation
  (OIDC) against this same existing Managed Identity for exactly this future pipeline — this
  PBI is the first to actually implement that recommendation.

### Design decisions (see `decisions.md` for full rationale)

1. Extend the existing `azure-pipelines.yml` in place — do not create a second, parallel
   pipeline file.
2. Reuse the existing Managed Identity for the Azure DevOps service connection (Workload
   Identity Federation) rather than creating a new identity or service principal.
3. Grant that identity exactly two new, narrowly-scoped roles (AcrPush on the ACR; Container
   Apps Contributor per Container App, not resource-group-wide) — the minimum needed for
   push + targeted update, nothing else.
4. Combine "Container Build" and "Push Images" into one YAML stage (two clearly-labeled step
   groups) — Azure Pipelines stages don't share a Docker image cache across stage boundaries.
5. Never run `az deployment group create`/`what-if` from the routine pipeline — only targeted
   `az containerapp update --image` calls, satisfying "do not recreate infrastructure."
6. Use a unique, versioned image tag (`dev-$(Build.BuildId)`) every run — never `latest` —
   which also structurally avoids the "same tag = no new revision" pitfall discovered during
   PBI-03-05/06's manual validation.
7. Resolve ACR/Container App names dynamically (`az acr list`/`az containerapp list` scoped to
   the one hardcoded, stable resource-group name) rather than hardcoding generated
   `uniqueString()`-suffixed names anywhere in the YAML.
8. Deploy-affecting stages gated to the `main` branch only (parameterized as `deployBranch`) —
   PR validation and `develop` pushes still run the full quality-gate suite but never deploy.

### Execution order

1. Bicep RBAC additions (`container-registry.bicep`, `container-app.bicep`, `main.bicep`) —
   validate statically only, do not deploy.
2. Rewrite `azure-pipelines.yml` — fix the two pre-existing defects, add Stages 4-8.
3. Validate: YAML syntax parse, manual schema/logic review, real read-only `az` CLI dry-run of
   every dynamic query and both smoke-test commands against the live DEV environment.
4. Full `pytest`/`ruff`/`mypy` regression run (no Python source touched, but required by the
   PBI's own validation list).
5. Document in `docs/sprint_04/{README,validation,decisions}.md` and `evidence/`.
6. Produce the PBI-04-01 Summary; stop. No commit, no push, no live Azure deployment, no real
   pipeline run — all pending explicit user review/approval.

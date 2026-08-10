# Sprint 07 Decisions and Deviations

Record sprint-specific decisions and deviations. Cross-sprint decisions belong in ADRs.

## 2026-08-10 — PBI-07-01: Extended the existing `azure-pipelines.yml` in place, again

**Decision:** Same precedent as PBI-04-01 (`docs/sprint_04/decisions.md`'s first entry): this
PBI edits the same, single `azure-pipelines.yml` file in place — adding a `SecurityScan` stage
and an `InfrastructureDeploy` stage, extending `ContainerBuildAndPush`/`DeployDev` with
Web-only-when-changed logic, and expanding `SmokeTests` — rather than creating a second,
competing pipeline file or a Classic pipeline.

**How to apply:** Any future pipeline stage should be added to this same file, following the
same `dependsOn`/`condition` gating pattern already established.

## 2026-08-10 — PBI-07-01: `InfrastructureDeploy`'s new RBAC grant is `Contributor` scoped to the resource group, deliberately not `Owner`

**Decision:** Running `az deployment group create` against the full `main.bicep` template from
an unattended CI identity requires meaningfully broader permissions than any RBAC this platform
has granted its CI identity before (PBI-04-01's `AcrPush`/`Container Apps Contributor` grants
are each scoped to one specific resource). `ops/bicep/main.bicep` gained a new, **off-by-default**
parameter, `cicdInfrastructureContributorPrincipalId` (empty string = no role assignment
created), which — when explicitly set — grants the built-in `Contributor` role
(`b24988ac-6180-42a0-ab88-20f7382dd24c`, confirmed against the live Azure role-definition
catalog, not guessed — same verification discipline as PBI-04-01's `AcrPush` role GUID),
**scoped to `rg-tmx-agent-platform-dev` only** (no explicit `scope:` on the role assignment
resource — it inherits the resource group scope of the template's own deployment, never
subscription-wide).

**Why `Contributor`, not `Owner`:** `Contributor` excludes `Microsoft.Authorization/*/write` —
this identity can create/update every resource type `main.bicep` declares (Storage, Web,
Cosmos, etc.) but **cannot** grant itself or anyone else a new role. `Owner` (`= Contributor +
User Access Administrator`) would additionally let this identity escalate its own privileges —
a materially different, much higher-risk grant this PBI does not ask for and CLAUDE.md §3's
"least privilege" principle argues against granting without a specific, demonstrated need.

**Known, accepted consequence:** `main.bicep` already declares several
`Microsoft.Authorization/roleAssignments` resources (the pre-existing data-plane roles for the
platform's Managed Identity, plus PBI-04-01's `AcrPush`/`Container Apps Contributor`, plus this
PBI's own new role assignment). A `Contributor`-only identity attempting to redeploy the full
template will hit an authorization error specifically on those `roleAssignments` sub-resources
on every run — expected, since those roles are already correctly applied and essentially never
change. This is a **known limitation of the design, not empirically tested** (the RBAC grant
itself is not yet applied to real Azure — see the "Deviation" note below), flagged honestly
rather than silently assumed away. Unlike the Function App quota condition (which the pipeline
script explicitly catches and treats as non-blocking, because it was empirically confirmed three
times this session), this authorization-on-roleAssignments condition is **not** given the same
special-case treatment in the pipeline script — if it occurs, `InfrastructureDeploy` will fail
loudly (a real, correct signal that role-assignment resources couldn't be reconciled), while
`DeployDev`/`SmokeTests` remain unaffected regardless (structural independence — see the next
entry).

**Deviation/status change:** A genuinely new, broader capability grant (the CI identity has
never held resource-group-level write access before), explicitly flagged for separate human
review — **not applied to the real DEV environment** by this PBI. Bicep support is additive and
off (`dev.bicepparam` does not set this parameter); applying it is a distinct, later,
explicitly-authorized action, following the exact same pattern PBI-04-01 used for its own RBAC
additions (Bicep written and validated first, applied to real Azure only after explicit
approval).

**How to apply:** Before `InfrastructureDeploy` can succeed against real Azure, someone with
Owner/User Access Administrator on the subscription must set
`cicdInfrastructureContributorPrincipalId` (in `dev.bicepparam` or via `az deployment group
create ... --parameters cicdInfrastructureContributorPrincipalId=<principalId>`) and run a
one-time, explicitly-approved `az deployment group create` — see `azure-devops-setup.md`.

## 2026-08-10 — PBI-07-01: `InfrastructureDeploy` is structurally independent of `DeployDev`/`SmokeTests` — belt and suspenders, not just error-swallowing

**Decision:** `DeployDev`'s `dependsOn` lists `ContainerBuildAndPush` and `InfrastructureValidation`
only — **not** `InfrastructureDeploy`. This is a structural guarantee, enforced by the pipeline
graph itself, that no infrastructure-deploy problem (the known Function App quota block, the new
RBAC not yet granted, or any other infra-only issue) can ever prevent API/Web container delivery
from running. The `InfrastructureDeploy` script's own quota-aware exit-0 handling (see the next
entry) is a second, independent safeguard for the one specific condition it recognizes — the
`dependsOn` design means even a genuinely unhandled `InfrastructureDeploy` failure still cannot
block `DeployDev`/`SmokeTests`.

**How to apply:** Any future stage whose failure should not gate API/Web delivery should follow
this same pattern — omit it from `DeployDev`'s `dependsOn` rather than relying solely on
condition logic or error-suppression inside that stage's own script.

## 2026-08-10 — PBI-07-01: Only ONE specific, empirically-confirmed error condition is treated as non-blocking in `InfrastructureDeploy`

**Decision:** The `InfrastructureDeploy` stage's script inspects a failed `az deployment group
create`'s full error output for exactly two substrings: `SubscriptionIsOverQuotaForSku` and
`Microsoft.Web/serverFarms`. Only when **both** are present does the script log a warning
(`##vso[task.logissue type=warning]`) and exit 0 (non-blocking). This exact error signature was
produced by **3 independent, real** `az deployment group create` attempts against
`rg-tmx-agent-platform-dev` this session (`Y1`, `B1`, and `P0v4` App Service Plan SKUs — see
`docs/sprint_06/decisions.md` D-07 and `docs/Architecture/adr/0003-azure-functions-tool-and-workflow-layer.md`),
copied verbatim, not guessed. Any other failure — a real Bicep defect, an authorization error, a
different Azure error — causes the script to `exit 1` and fail the stage for real. This is a
narrow, evidence-backed exception, not a blanket "ignore deployment errors" pattern.

**Deviation/status change:** None — directly implements this PBI's own explicit instruction:
"the pipeline must be READY to deploy those resources when quota is enabled, but this external
blocker must not incorrectly mark unrelated API/Web delivery as failed. Document this behavior
clearly."

**How to apply:** If the Azure subscription's App Service quota is ever granted, this exact
condition simply stops occurring — `InfrastructureDeploy` will report `succeeded` instead of
`partial-quota-blocked` (see `DeploymentSummary`'s reporting of `infraDeployResult`), with no
pipeline change required. If a *different* external, documented, expected-to-recur condition is
discovered in the future, add its own specific substring match — never widen the existing check
to something generic like "any Azure error is fine."

## 2026-08-10 — PBI-07-01: Security tool findings — real, current, evidence-backed gate design, not guessed thresholds

**Decision:** Before writing the `SecurityScan` stage, all three tools were run locally against
this repository's real, current state (2026-08-10) to confirm the gate would be meaningful, not
permanently red or a rubber stamp:

1. **`pip-audit`** — run against a freshly-created, isolated venv installing *exactly* the
   `BackendQuality`/`SecurityScan` stage's own pinned dependency list (not this development
   session's much larger local environment, which includes unrelated Jupyter/ML/notebook
   tooling and would have produced a wildly misleading "64 vulnerabilities" result). Real
   result: 2 packages, 8 findings.
   - `setuptools 65.5.0` (4 distinct CVEs, fixed in versions 65.5.1 through 83.0.0): bundled
     packaging tooling, not a declared project dependency, never imported by application code.
     **Fixed directly** — the `SecurityScan` stage now runs
     `pip install --upgrade "setuptools>=78.1.1"` before auditing. Confirmed this alone clears
     all 4 setuptools findings.
   - `pytest 8.4.2` (`PYSEC-2026-1845`, fixed only in `pytest>=9`): `apps/api/pyproject.toml`
     pins `pytest>=8.2,<9` deliberately — this repository's test suite has never been validated
     against pytest 9's breaking changes, a real, separately-scoped upgrade decision this CI/CD
     PBI should not make unilaterally. pytest also never ships in the deployed container
     (test-only tool). **Ignored explicitly** via `pip-audit --ignore-vuln PYSEC-2026-1845`,
     with this justification inline in the pipeline comment — not silently dropped.
   - Confirmed clean (exit 0) with both changes applied.
2. **`npm audit`** — `apps/web`'s real `package-lock.json`. Full audit (including
   `devDependencies`): 5 findings (1 critical, 1 high, 3 moderate), all transitively via
   `esbuild`/`vite`/`vitest` — build/test tooling only, never shipped in the production build
   (`apps/web/Dockerfile` serves the built `dist/` output, not `node_modules`); fixing requires
   `npm audit fix --force`, a breaking Vite major-version bump — an out-of-scope build-toolchain
   upgrade. `apps/web/package.json`'s actual `dependencies` (not `devDependencies`) are exactly
   `react`/`react-dom`. `npm audit --omit=dev` against just those: **0 vulnerabilities**. The
   gate uses `--omit=dev` as the hard, blocking check (the real, shipped production risk
   surface); the full audit (including dev tooling) is published as a non-blocking,
   informational report for visibility.
3. **`detect-secrets`** — a full repository scan (excluding `node_modules`/`.venv`, which are
   gitignored and would never exist in a fresh CI checkout) found 7 candidate matches, all
   confirmed by hand to be false positives: 5 in source/test code (parameter/variable NAMES
   containing "secret" — `secretName`, `SecretProvider`, `secret_provider=`,
   `api_key_secret_name=`, `key_vault_uri="https://example.vault.azure.net/"` — never an actual
   value) and 2 in `docs/**/evidence/*.txt` (a real Ollama model SHA256 digest and an OpenAI
   tool-call ID, both high-entropy-looking but not secrets). The 5 source-level false positives
   are suppressed with inline `# pragma: allowlist secret` comments at their exact line
   (`detect-secrets`'s own supported mechanism — auditable in code review, no separate baseline
   file to maintain or accidentally go stale). The 2 evidence-file findings are excluded by path
   (`--exclude-files 'docs/.*/evidence/.*'`) rather than edited — those files are frozen,
   historical validation records (CLAUDE.md §12: "do not erase previous entries").
   Re-confirmed clean (0 results) after applying both.

**Deviation/status change:** Five pre-existing files
(`ops/bicep/main.bicep`, `src/services/secret_store/factory.py`,
`tests/unit/llm/test_azure_openai_provider.py`, `tests/unit/rag/test_azure_ai_search_provider.py`,
`tests/unit/services/test_secret_provider_factory.py`) each gained one or two
`# pragma: allowlist secret` / `// pragma: allowlist secret` inline comments — no logic change,
purely a security-tooling annotation, necessary for the new gate to be usable (a permanently-red
gate trains reviewers to ignore it, which is worse than no gate at all).

**How to apply:** Do not widen `--ignore-vuln`/`--omit=dev`/pragma-comment usage beyond what is
documented here without the same evidence-backed justification. If `apps/web`'s
`dependencies` ever grow beyond `react`/`react-dom`, re-run this same validation before trusting
`--omit=dev` remains a meaningful gate boundary. If `pytest` is ever upgraded past 9.x in a
dedicated PBI, remove the `--ignore-vuln PYSEC-2026-1845` exception in the same change.

## 2026-08-10 — PBI-07-01: Web-only-when-changed compares against the immediate parent commit (`HEAD^`), not a merge-base or last-successful-deploy commit

**Decision:** `ContainerBuildAndPush`'s `detectWebChange` step runs
`git diff --name-only HEAD^ HEAD -- apps/web` (after `checkout: self` with `fetchDepth: 2`, so
`HEAD^` is guaranteed to exist for any normal push). This is a pragmatic, "good enough" choice
for this project's branching model (`docs/sprint_04/decisions.md`: deploy-affecting stages only
run on pushes to `main`, each typically a single merge/squash commit representing one whole
PR) — it correctly captures a PR's entire diff in one comparison. This project has no `develop`
or other long-lived integration branch to diff against (PBI-07-01B; `main`/`feat/*`/`fix/*`/
`review/*` only — CLAUDE.md §15), so it does **not** attempt a merge-base comparison, nor track
the last-successfully-deployed commit (which would require persisting state between pipeline
runs, e.g., a pipeline variable group or a tag — added complexity not justified for this
project's flow). If `HEAD^` cannot be resolved (e.g. the very first commit in the repository's
history), the check defaults to `changed=true` (always build) rather than silently skipping — a
safe default for an edge case the check cannot reason about.

**How to apply:** If this project's branching model changes to routinely land multiple discrete
commits directly on `main` per logical change (not the current single-merge-commit flow), revisit
this comparison — `git diff --name-only $(git merge-base origin/main HEAD) HEAD -- apps/web`
would be the next-more-robust option for a run still on a feature branch, at the cost of
requiring `main` to be fetched too (this comment applies to `ContainerBuildAndPush`, which only
ever runs on `main` pushes themselves — for `ContainerBuildValidation`'s own, independent
same-logic copy on `feat/*`/`fix/*`/`review/*` branches, "the immediate parent commit" already
means "the previous commit on this feature branch," which is the correct comparison target
there today).

## 2026-08-10 — PBI-07-01: Image tag traceability uses the full commit SHA, not a shortened one

**Decision:** `imageTag` changed from `dev-$(Build.BuildId)` to
`dev-$(Build.BuildId)-$(Build.SourceVersion)` — `Build.SourceVersion` is Azure Pipelines' own
predefined variable for the full, 40-character commit SHA, requiring no extra script step to
compute. Docker tags allow up to 128 characters, so the longer tag has no practical downside,
and a full SHA is unambiguous (`git show <tag-suffix>` always resolves correctly, unlike a
truncated/shortened SHA which carries a — extremely small but non-zero — collision risk).

**How to apply:** Do not reintroduce a shortened/computed SHA via an extra script step unless a
concrete requirement (e.g., a tag-length limit from some other tool) actually needs it.

## 2026-08-10 — PBI-07-01A: Corrected the service connection identity assumption with live evidence, not another guess

**Decision:** PBI-07-01 assumed (per `docs/sprint_00/security-baseline.md` §6's original
recommendation) that the Azure DevOps service connection would target the platform's existing
user-assigned Managed Identity, `id-tmxap-dev`. The user reported this did not happen — the real
service connection (`sc-tmx-agent-platform-dev`, project `Enterprise-ai-multiagent-reference`,
org `tokio-marine-mx-devops`) was created via Azure DevOps's "App registration (automatic)"
flow, which creates its own Entra ID App Registration rather than targeting an existing identity.
Rather than take this claim at face value and guess at the consequences, it was verified live:

```
az role assignment list --resource-group rg-tmx-agent-platform-dev
```
Result: exactly one role assignment beyond the resource-specific ones already known — a
`ServicePrincipal` (shown only as a GUID, `e35d2b19-6ac8-41e5-af14-66a9095d4e35`, since
`az role assignment list` couldn't resolve a friendly name for a principal outside typical
directory-read scope) holding **`Contributor`** at the resource-group scope.

```
az ad sp show --id e35d2b19-6ac8-41e5-af14-66a9095d4e35
```
Result: `displayName`
"tokio-marine-mx-devops-Enterprise-ai-multiagent-referen-01f72900-d947-4518-a530-c2fd1d9dd361",
object id `9f6190e9-b5dd-4651-a90b-45d9f37bcc5a` — an Azure-DevOps-generated display name
pattern (org-project-connectionId), not `id-tmxap-dev`.

```
az ad app federated-credential list --id e35d2b19-6ac8-41e5-af14-66a9095d4e35
```
Result: one federated credential, `description`: *"Federation for Service Connection
sc-tmx-agent-platform-dev in
https://dev.azure.com/tokio-marine-mx-devops/Enterprise-ai-multiagent-reference/..."* — **this
is definitive, unambiguous confirmation** that this exact service principal is the real identity
backing `sc-tmx-agent-platform-dev`, not an assumption.

**Deviation/status change:** PBI-07-01's identity assumption was wrong; corrected here with
evidence, not merely accepted on the user's word. Every RBAC-relevant comment and the
`azureServiceConnection` parameter default in `azure-pipelines.yml`, and the `cicdInfrastructureContributorPrincipalId`
description in `ops/bicep/main.bicep`, updated to reference the real principal
(`9f6190e9-b5dd-4651-a90b-45d9f37bcc5a`) instead of `id-tmxap-dev`.

**How to apply:** Never assume which principal backs an Azure DevOps service connection —
`az ad app federated-credential list --id <appId>` reliably confirms it by matching the
federated credential's own `description` field, which Azure DevOps populates with the exact
service connection name and project URL. Use this same verification method for any future
service connection this project creates.

## 2026-08-10 — PBI-07-01A: The real service connection principal already holds Contributor on the resource group — no new Bicep-driven RBAC grant is needed

**Decision:** The live `az role assignment list` result above means the real pipeline identity
already holds exactly the role PBI-07-01's `cicdInfrastructureContributorPrincipalId` parameter
was designed to grant — `Contributor`, scoped to `rg-tmx-agent-platform-dev` — except it was
granted **automatically by Azure DevOps itself** at service-connection-creation time (a standard
behavior of the "automatic" Workload Identity Federation flow when scoped to a resource group),
**not** by this repository's Bicep. `Contributor`'s own definition (`Actions: ["*"]`, excluding
only `Microsoft.Authorization/*/write` and a handful of Blueprint/Purview actions) already covers
every action `ContainerBuildAndPush` (ACR push), `DeployDev` (Container App image update), and
`InfrastructureDeploy` (general resource deployment) need. Per this PBI's explicit instruction
("Do not make new RBAC changes automatically" / "Do NOT assign Contributor to id-tmxap-dev
merely because the earlier design assumed that identity"), **no RBAC change was made** — Bicep's
`cicdInfrastructureContributorPrincipalId` remains unset in `dev.bicepparam`, and `id-tmxap-dev`
was not touched.

**Exact principal the role is already on, if this is ever codified into IaC:** service principal
object id `9f6190e9-b5dd-4651-a90b-45d9f37bcc5a` (appId `e35d2b19-6ac8-41e5-af14-66a9095d4e35`) —
**not** `id-tmxap-dev`'s principal id.

**Known limitation of this finding:** confirmed via the human user's own Owner-level `az`
session inspecting Azure state (a read-only `az role assignment list`/`az ad sp show`/`az ad app
federated-credential list`), **not** via a live OIDC token exchange through
`sc-tmx-agent-platform-dev` itself actually running `az deployment group create`. The
`InfrastructureDeploy` stage's known-error handling (see the prior PBI-07-01 entry on this) only
special-cases the `SubscriptionIsOverQuotaForSku`/`Microsoft.Web/serverFarms` signature — it does
NOT special-case a potential `Microsoft.Authorization/roleAssignments` authorization failure
(anticipated, since `Contributor` excludes that action, but not given the same exit-0 treatment
because its exact error text has never been empirically observed against this identity). If it
occurs on a real run, `InfrastructureDeploy` will fail loudly for that reason — correctly
visible, not silently swallowed — while `DeployDev`/`SmokeTests` remain structurally unaffected
regardless (unchanged from the PBI-07-01 design).

**Consequence for `id-tmxap-dev`'s PBI-04-01 CI roles:** `AcrPush` and `Container Apps
Contributor`, granted to `id-tmxap-dev` in PBI-04-01 specifically so the (assumed)
pipeline-identity could push images and update Container Apps, are now confirmed **unused by the
actual CI/CD pipeline** — the pipeline authenticates as a different principal entirely. These
grants remain in place on `id-tmxap-dev` (harmless — that identity still legitimately needs
`AcrPull` for its own runtime image-pulling role, unaffected by this) but are effectively dead
weight for their originally-intended CI purpose. **Not removed** — a cleanup of unused RBAC is a
separate, not-yet-authorized action; flagged here as known technical debt for a future PBI.

**How to apply:** If a future decision is made to bring this already-existing external
Contributor grant under IaC control (so `git blame`/Bicep alone tells the whole RBAC story
without cross-referencing this decisions file), set
`cicdInfrastructureContributorPrincipalId=9f6190e9-b5dd-4651-a90b-45d9f37bcc5a` in
`dev.bicepparam` and redeploy — Bicep's role-assignment resource uses a deterministic `guid(...)`
name, so this redeploy would be a true no-op against the already-existing Azure state (same
role, same principal, same scope), not a duplicate/conflicting grant. A separate, future PBI
should decide whether to remove `id-tmxap-dev`'s now-unused `AcrPush`/`Container Apps
Contributor` roles.

## 2026-08-10 — PBI-07-01: No live Azure DevOps organization access — validation-only scope, mirrors PBI-04-01's precedent exactly

**Decision:** Consistent with PBI-04-01's own "Pipeline validation was static/offline only" entry
and this PBI's own explicit instruction ("Do targeted local validation only... stop and report
the exact manual Azure DevOps setup required"), this PBI's validation is: `python
yaml.safe_load` (full pipeline parses), `az bicep build`/`build-params` (the new
`cicdInfrastructureContributorPrincipalId` parameter and role assignment compile cleanly), and
real local tool runs for the Security stage's three tools (see the dedicated entry above) — not
a live Azure DevOps pipeline trigger, not a real `az deployment group create` from
`InfrastructureDeploy`, not a real `az containerapp update`. `az devops configure -l` was
confirmed (again) to fail with no organization context, exactly as PBI-04-01 found.

**How to apply:** The next session with real Azure DevOps organization access must, in order:
(1) create the service connection; (2) decide whether to apply the new
`cicdInfrastructureContributorPrincipalId` RBAC grant (a separate approval from the service
connection's own creation); (3) push to `main` or trigger the pipeline manually; (4) observe the
real run, paying particular attention to whether `InfrastructureDeploy`'s quota-aware handling
behaves as designed against the pipeline's own service-connection identity (not yet
empirically confirmed — only this session's user-credential-based `az` calls were). See
`azure-devops-setup.md` for the full step-by-step sequence.

## 2026-08-10 — PBI-07-01A: Validation scope — reconciliation only, still no live pipeline run, no deployment

**Decision:** This PBI's own explicit instructions ("Do not deploy. Do not commit. Do not
push.") scope it to documentation/reconciliation only. Validation performed: re-ran `python
yaml.safe_load` and `az bicep build` after all edits (both clean); confirmed via `grep` that no
remaining reference to the old assumed service connection name
(`tmx-agent-platform-dev-oidc`) or an incorrect `id-tmxap-dev`-as-pipeline-identity claim
remains in any forward-looking file (`azure-pipelines.yml`, `docs/sprint_07/*.md`) — historical
records in `docs/sprint_04/decisions.md` were deliberately left untouched (they correctly
document what was believed and done at that time; CLAUDE.md §12 "do not erase previous
entries"). No `az deployment group create`, no `az containerapp update`, no real Azure DevOps
pipeline trigger.

**Supersedes:** the prior entry's "How to apply" step (1) — the service connection now exists;
do not attempt to create a second one. Steps (3)-(4) of that entry remain the accurate
next-action sequence, now updated in `azure-devops-setup.md` directly rather than restated here.

**How to apply:** See `azure-devops-setup.md`'s own "Remaining steps" section — it is the
authoritative, current setup checklist as of this entry, superseding the equivalent section this
same file described before PBI-07-01A.

## 2026-08-10 — PBI-07-01B: Corrected the trigger/PR branch strategy to this project's real Git workflow (no `develop`)

**Decision:** `azure-pipelines.yml`'s `trigger.branches.include` changed from `[develop, main]`
to `[main, feat/*, fix/*, review/*]`; `pr.branches.include` changed from `[develop, main]` to
`[main]` only. This project has never used a `develop` branch (CLAUDE.md §15's branch model has
always been `feature/*`/`infra/*`/`fix/*` off `main`, no long-lived integration branch) — the
original PBI-00-07/PBI-04-01 pipeline design carried over a generic `develop` assumption that
was never actually correct for this repository. `docs/**`/`**/*.md` path exclusion preserved
unchanged (requirement 5 — no genuine need for CI on documentation-only changes was identified).

**Deviation/status change:** A real, previously-undetected mismatch between the pipeline's
assumed branching model and this project's actual one, corrected on explicit instruction — not
a design change to CI logic itself (deploy-gating, stage structure, security/quality gates all
unchanged).

**How to apply:** If a new long-lived branch prefix is ever adopted, add it to `trigger.branches.include`
only — `pr.branches.include` should stay `[main]` alone unless this project starts accepting PRs
into more than one target branch.

## 2026-08-10 — PBI-07-01B: Added `ContainerBuildValidation` — a real "does this image build" check for feat/fix/review branches, with zero Azure exposure

**Decision:** Per explicit instruction (clarified via a direct question — see the conversation:
requirement 3 lists "Build" among what feature branches "may run," while requirement 4's
explicit main-only list names only `InfrastructureDeploy`/`DeployDev`/`SmokeTests`, not
`ContainerBuildAndPush`), added a new stage, `ContainerBuildValidation`: plain `docker build`
for the API image (always) and the Web image (only when `apps/web` changed, reusing the same
`git diff HEAD^ HEAD` logic `ContainerBuildAndPush`/`DeployDev` already use), with **no** `az
acr login`, **no** `docker push`, **no** `AzureCLI@2` task, **no** service-connection reference
of any kind — this stage cannot authenticate to Azure even if it wanted to, by construction, not
merely by convention. `condition: and(succeeded(), ne(variables.isDeployRun, true))` — the exact
logical complement of `ContainerBuildAndPush`'s own `eq(variables.isDeployRun, true)` — so it
runs on every PR-against-main and every `feat/*`/`fix/*`/`review/*` push, and never on a `main`
push (avoiding a redundant second build there; `ContainerBuildAndPush`'s own build already
covers `main`, and is a strict superset — it also pushes).

**Deviation/status change:** A genuine, scoped behavior addition beyond a pure trigger/condition
edit (the user's own framing was "Update ONLY the Azure Pipelines branch strategy," and this
does add a new stage) — done only after asking the user directly whether this was in scope, per
CLAUDE.md's own guidance to clarify genuine ambiguity rather than guess on a real design fork;
user chose to add it.

**How to apply:** If a Web image build ever needs a non-default `VITE_API_URL` to validate
correctly (unlikely — Vite bundles whatever string is given; the Dockerfile's own default,
`http://localhost:8000`, is sufficient for a "does it build" check), pass
`--build-arg VITE_API_URL=<placeholder>` explicitly in this stage's Web build step, mirroring
`ContainerBuildAndPush`'s own `--build-arg` usage — not done today because it isn't needed.

## 2026-08-10 — PBI-07-01B: Verified every deploy-affecting stage is self-gated, not merely dependency-gated

**Decision:** Re-confirmed (via `python -c "import yaml; ..."` printing every stage's
`dependsOn`/`condition`) that `InfrastructureDeploy`, `ContainerBuildAndPush`, `DeployDev`,
`SmokeTests`, and `DeploymentSummary` each carry `eq(variables.isDeployRun, true)` (or the
equivalent `dependencies.*.result` form for `DeploymentSummary`) **in their own `condition`**,
not only inherited via a `dependsOn` chain — Azure Pipelines does not cascade a dependency's
condition to its dependents automatically, so a stage that depended on a gated stage without its
own gate could still be independently triggered depending on how its own condition evaluates.
Every deploy-affecting stage passed this check; no change was needed as a result (the design was
already correct from PBI-07-01/07-01A), but the verification itself is the deliverable this
requirement asked for.

**How to apply:** Any future new deploy-affecting stage must include its own explicit
`eq(variables.isDeployRun, true)` (or equivalent) — never rely solely on `dependsOn` a gated
stage to inherit that protection.

# Sprint 07 — Validation

All commands below were actually executed in this session, from the repository root. No live
Azure mutation, no `az deployment group create`, no `az containerapp update`, no real Azure
DevOps pipeline run — consistent with this PBI's own "targeted local validation only" scope
(see `decisions.md`'s final entry).

## Pipeline YAML syntax

```
python -c "
import yaml
with open('azure-pipelines.yml', encoding='utf-8') as f:
    data = yaml.safe_load(f)
print('YAML parses OK, stages:', len(data['stages']))
"
```
Result: **YAML parses OK, stages: 10** — `BackendQuality`, `FrontendQuality`, `SecurityScan`,
`InfrastructureValidation`, `InfrastructureDeploy`, `ContainerBuildAndPush`, `DeployDev`,
`SmokeTests`, `DeploymentSummary`, `ArtifactPublication`. Ran twice (before and after the final
header/comment cleanup pass) — both clean.

## Bicep compilation (new RBAC parameter + role assignment)

```
az bicep build --file ops/bicep/main.bicep --stdout
```
Result: compiles cleanly, exit 0. `grep -c "cicdInfrastructureContributor"` on the compiled JSON
output: **6** references present (parameter, variable, resource, and its property bindings) —
confirms the new opt-in RBAC block is syntactically valid and wired correctly.

```
az bicep build-params --file ops/bicep/parameters/dev.bicepparam --outfile <tmp>
```
Result: exit 0 — `dev.bicepparam` still resolves against `main.bicep`'s parameter contract
unchanged (the new parameter is optional with a default, so the existing parameter file needed
no edit).

## Task references, conditions, variable flow — manual review

- Confirmed `DeployDev`'s `dependsOn` lists `ContainerBuildAndPush`/`InfrastructureValidation`
  only, never `InfrastructureDeploy` — the structural guarantee that infra-deploy issues cannot
  block container delivery (`decisions.md`).
- Confirmed `DeploymentSummary`'s `condition` uses `dependencies.<Stage>.result` (not a blanket
  `succeeded()`) specifically so it still publishes when `InfrastructureDeploy` reports anything
  other than `Succeeded` — this is documented, standard Azure Pipelines YAML stage-condition
  syntax (`dependencies.<stageName>.result`), used here for the same reason PBI-04-01 already
  used `stageDependencies.<Stage>.<Job>.outputs[...]` for cross-stage variable reads.
  Cross-checked against the file's own pre-existing, already-proven use of `stageDependencies`
  for `apiFqdn`/`apiAppName`/etc.
- Confirmed every new cross-stage variable reference (`webChanged`, `infraDeployResult`,
  `apiAppName` in `SmokeTests`) has its source stage listed in the consuming stage's own
  `dependsOn` — a `stageDependencies` reference to a stage not in `dependsOn` cannot resolve.
- Confirmed the `InfrastructureDeploy` script's quota-handling branch: `set +e` around exactly
  the `az deployment group create` call (never around `validate`, since `validate` was
  empirically observed in PBI-06-01A to succeed even when the subsequent `create` fails on the
  quota condition — `set -e` correctly resumes immediately after capturing `create`'s exit code).

## Security tooling — real, local runs against this repository's current state (2026-08-10)

### pip-audit

Installed an isolated venv (`python -m venv`) with **exactly** the `BackendQuality`/
`SecurityScan` stage's own pinned dependency list (not this development session's own, much
larger, environment):

```
pip install "fastapi>=0.115,<1" "uvicorn[standard]>=0.30,<1" "pydantic>=2.7,<3" \
  "pydantic-settings>=2.3,<3" "pytest>=8.2,<9" "httpx>=0.27,<1" "ruff>=0.5,<1" "mypy>=1.10,<2" \
  "pytest-asyncio>=0.23,<1" "azure-cosmos>=4.7,<5" "azure-identity>=1.17,<2" \
  "azure-keyvault-secrets>=4.8,<5" "openai>=1.40,<2" "aiohttp>=3.9,<4" "pytest-cov>=5,<7" \
  "pip-audit>=2.7,<3"
pip-audit --progress-spinner off --format json -o <tmp>
```
Result (before any fix): **8 known vulnerabilities in 2 packages** — `pytest 8.4.2`
(`PYSEC-2026-1845`) and `setuptools 65.5.0` (`PYSEC-2022-43012` ×2, `PYSEC-2025-49` ×2,
`PYSEC-2026-1918`, `PYSEC-2026-3447`).

```
pip install --upgrade "setuptools>=78.1.1"
pip-audit --progress-spinner off --format json -o <tmp> --ignore-vuln PYSEC-2026-1845
```
Result: **exit 0, zero remaining findings** — confirms the `SecurityScan` stage's exact
`setuptools` upgrade + `--ignore-vuln` combination produces a clean, meaningful gate against
this repository's real, current dependency set.

### npm audit

```
cd apps/web && npm audit --audit-level=high
```
Result: **exit 1** — 5 vulnerabilities (1 critical, 1 high, 3 moderate), all transitively via
`esbuild`/`vite`/`vitest` (confirmed via the report's own dependency tree — all under
`devDependencies`).

```
python -c "import json; d=json.load(open('package.json')); print(d['dependencies'], d['devDependencies'])"
```
Result: `dependencies` = `{react, react-dom}` only; every flagged package is in
`devDependencies`.

```
npm audit --omit=dev --audit-level=high
```
Result: **exit 0, "found 0 vulnerabilities"** — confirms the `SecurityScan` stage's
production-dependencies-only gate is currently clean, and confirms the informational full-audit
report (kept non-blocking) is the correct place for the 5 dev-tooling-only findings.

### detect-secrets

```
python -m detect_secrets scan src apps/api/src apps/web/src ops configs tests --all-files
```
(First pass, before edits) Result: **7 files flagged** — `ops/bicep/main.bicep:233`,
`src/services/secret_store/factory.py:17,20`, `tests/unit/llm/test_azure_openai_provider.py:208`,
`tests/unit/rag/test_azure_ai_search_provider.py:273`,
`tests/unit/services/test_secret_provider_factory.py:23`, plus 2 in `docs/**/evidence/*.txt`
(found via a separate, unscoped run). Every flagged line inspected by hand (`sed -n` on the
exact line numbers) and confirmed benign — parameter/variable NAMES (`secretName`,
`SecretProvider`, `secret_provider=`, `api_key_secret_name=`) or historical evidence-log content
(an Ollama model SHA256 digest, an OpenAI tool-call ID) — never an actual credential value.

After adding inline `# pragma: allowlist secret` / `// pragma: allowlist secret` comments to
the 5 source-level findings (some required 2 attempts — the plugin de-duplicates identical
secret values within a file and reports the *next* occurrence once the first is suppressed;
both files with a duplicated string value needed the pragma on both lines):

```
python -m detect_secrets scan src apps/api/src apps/web/src ops configs tests --all-files
```
Result: **0 files flagged** — confirms the pragma-comment suppressions fully resolve the
source-level false positives, matching exactly the invocation the `SecurityScan` stage's
`detect-secrets` step uses (`--exclude-files 'docs/.*/evidence/.*'` handles the remaining 2
evidence-file findings by path, not by editing frozen historical records).

## Not performed (explicitly, per this PBI's own scope)

- No real Azure DevOps organization/PAT is configured in this or any prior session —
  `az devops configure -l` fails with no organization context (re-confirmed this session,
  identical to PBI-04-01's own finding). The service connection cannot be created, and no real
  pipeline run could be triggered.
- No live `az deployment group create` was run from `InfrastructureDeploy`'s own script this
  PBI — its quota-aware error-matching logic is built from 3 real attempts made in a **prior**
  session (PBI-06-01/06-01A, using the user's own Azure credentials, not the pipeline's
  service-connection identity) and is not yet empirically confirmed against that identity.
- No `az containerapp update` was run — `DeployDev`'s Web-only-when-changed logic was verified
  by code review and the `git diff` mechanism's own local testability, not a live Container App
  update.
- The new `cicdInfrastructureContributorPrincipalId` RBAC grant was not applied to the real DEV
  environment (`dev.bicepparam` does not set it) — see `decisions.md`.

## PBI-07-01B (branch strategy correction) — 2026-08-10

```
python -c "
import yaml
with open('azure-pipelines.yml', encoding='utf-8') as f:
    data = yaml.safe_load(f)
print('trigger:', data['trigger'])
print('pr:', data['pr'])
"
```
Result:
```
trigger: {'branches': {'include': ['main', 'feat/*', 'fix/*', 'review/*']}, 'paths': {'exclude': ['docs/**', '**/*.md']}}
pr: {'branches': {'include': ['main']}}
```

```
python -c "
import yaml
with open('azure-pipelines.yml', encoding='utf-8') as f:
    data = yaml.safe_load(f)
for s in data['stages']:
    print(s.get('stage'), '| dependsOn:', s.get('dependsOn'), '| condition:', s.get('condition'))
"
```
Result (full stage graph, confirming every deploy-affecting stage is self-gated):
```
BackendQuality              | dependsOn: None | condition: None
FrontendQuality             | dependsOn: None | condition: None
SecurityScan                | dependsOn: None | condition: None
InfrastructureValidation    | dependsOn: None | condition: None
InfrastructureDeploy        | dependsOn: [InfrastructureValidation] | condition: and(succeeded(), eq(variables.isDeployRun, true))
ContainerBuildValidation    | dependsOn: [BackendQuality, FrontendQuality, SecurityScan] | condition: and(succeeded(), ne(variables.isDeployRun, true))
ContainerBuildAndPush       | dependsOn: [BackendQuality, FrontendQuality, SecurityScan] | condition: and(succeeded(), eq(variables.isDeployRun, true))
DeployDev                   | dependsOn: [ContainerBuildAndPush, InfrastructureValidation] | condition: and(succeeded(), eq(variables.isDeployRun, true))
SmokeTests                  | dependsOn: [DeployDev] | condition: and(succeeded(), eq(variables.isDeployRun, true))
DeploymentSummary           | dependsOn: [SmokeTests, DeployDev, ContainerBuildAndPush, InfrastructureDeploy] | condition: and(eq(variables.isDeployRun, true), in(dependencies.SmokeTests.result,'Succeeded'), in(dependencies.DeployDev.result,'Succeeded'), in(dependencies.ContainerBuildAndPush.result,'Succeeded'))
ArtifactPublication         | dependsOn: [InfrastructureValidation] | condition: None
```

Manual review confirms: `InfrastructureDeploy`, `ContainerBuildAndPush`, `DeployDev`,
`SmokeTests` (the exact set requirement 4 named) each carry `eq(variables.isDeployRun, true)` in
their OWN `condition` — not merely inherited via `dependsOn` — and `isDeployRun` itself
(`$[eq(variables['Build.SourceBranch'], 'refs/heads/${{ parameters.deployBranch }}')]`,
`deployBranch` default `main`) is an exact string-equality comparison, so no `feat/*`/`fix/*`/
`review/*` branch name or PR build (`refs/pull/<id>/merge`) can ever satisfy it. No deploy stage
is reachable indirectly: `ContainerBuildValidation`'s condition
(`ne(variables.isDeployRun, true)`) is the exact logical complement of
`ContainerBuildAndPush`'s, so the two are mutually exclusive on every run — confirmed no run can
trigger both.

```
grep -n "develop" azure-pipelines.yml
```
Result: only 2 matches, both explicitly stating "this project has no `develop` branch" (the
PBI-07-01B correction itself) — no residual behavioral reference.

```
az bicep build --file ops/bicep/main.bicep --stdout
```
Result: unaffected by this PBI (no Bicep files changed) — re-run only as a sanity check; exit 0,
unchanged from PBI-07-01A's own validation.

Not performed (per this PBI's explicit "Do not deploy. Do not commit. Do not push."): any real
Azure DevOps trigger, any `git push` to exercise the new branch patterns live.

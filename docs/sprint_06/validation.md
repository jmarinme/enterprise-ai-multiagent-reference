# Sprint 06 — Validation

All commands below were actually executed in this session, from the repository root, using the
project's `.venv`.

## Backend tests

```
./.venv/Scripts/python.exe -m pytest tests/ -q
```
Result: **577 passed, 2 skipped** (551 pre-existing + 26 new: 6 `ToolProvider`, 3
`InProcessClaimsWorkflowProvider`, 6 `DurableClaimsWorkflowProvider`, 3+3 factory tests, 5
`advance_claims_intake` workflow-provider integration tests). The 2 skipped tests pre-date this
PBI. The pre-existing 64-test Claims suite (`tests/unit/agents/claims/`,
`tests/unit/agents/test_claims_agent_*.py`) passed **unchanged** — zero test edits required for
the `ClaimsAgent`/`advance_claims_intake` rewire.

## Lint

```
./.venv/Scripts/python.exe -m ruff check apps/api/src src tests ops/scripts
```
Result: **All checks passed** (matches `azure-pipelines.yml`'s exact invocation).

```
./.venv/Scripts/python.exe -m ruff check ops/functions/claims_tools/function_app.py
```
Result: **All checks passed**.

## Type checking

```
./.venv/Scripts/python.exe -m mypy apps/api/src
./.venv/Scripts/python.exe -m mypy src
```
Result: **Success: no issues found** (14 files, 121 files — matches
`azure-pipelines.yml`'s exact invocation and working directory).

## Azure Functions app — direct functional smoke tests

Azure Functions Core Tools (`func`) could not be installed in this environment (npm install
failed: `Azure.Functions.Cli.win-x64.4.13.2.zip` returned HTTP 404 from the Functions CDN) — no
local `func start` host was available. `azure-functions`/`azure-functions-durable` Python SDKs
were installed directly, and `ops/functions/claims_tools/build.ps1` was run to vendor
repo-root `src/` into the Function App directory (mirrors `apps/api/Dockerfile`'s own
repo-root `src/` COPY). The HTTP handler and every Durable activity function were then invoked
directly as plain Python coroutines, against the real synthetic Tool data:

- `tools_http` (HTTP-triggered): `POST /api/tools/policy_lookup` with
  `X-Correlation-ID: corr-smoke-1` → HTTP 200,
  `{"tool_name":"policy_lookup","success":true,"data":{...},"correlation_id":"corr-smoke-1"}` —
  correlation ID round-tripped correctly.
- `policy_lookup_activity`, `claim_registration_activity`, `adjuster_assignment_activity`:
  chained manually (policy lookup → register a claim → assign an adjuster using the real
  generated `claim_reference`) — all three returned `success: true` with correctly-shaped data
  (`SYN-CLM-2026-0001`, a real `SyntheticAdjusterRecord`).

This confirms the Function App's Python code is correct and the vendored-`src/` import strategy
works, but is **not** a substitute for an actual Durable Functions host run — the generator-based
orchestrator (`claims_workflow_orchestrator`) itself was not executed end-to-end through the
Durable Task extension, since that requires a running Functions host. `DurableClaimsWorkflowProvider`
and `AzureFunctionToolProvider` (the API-side HTTP clients) were tested against a real local
`aiohttp` server (`tests/unit/core/tool_provider/test_azure_function_tool_provider.py`,
`tests/unit/core/workflow_provider/test_durable_workflow_provider.py`) simulating the exact
Azure Functions/Durable Functions HTTP contracts (starter response shape, `statusQueryGetUri`
polling, `runtimeStatus` transitions) — this covers the client side of the contract with real
HTTP, not the server side.

## Bicep

```
az bicep build --file ops/bicep/main.bicep --stdout
```
Result: compiles cleanly (17 references to the new Storage/Web resource types confirmed present
in the compiled template).

```
az deployment group validate \
  --resource-group rg-tmx-agent-platform-dev \
  --template-file ops/bicep/main.bicep \
  --parameters ops/bicep/parameters/dev.bicepparam
```
Result: **`provisioningState: "Succeeded"`** against the real DEV resource group, with
`function-app-storage-deployment` and `claims-tools-function-app-deployment` both listed in
`validatedResources`. `az deployment group what-if` was also run but was inconclusive for the
new resources — a pre-existing, unrelated ARM limitation
(`NestedDeploymentShortCircuited`, triggered by `containerAppsEnvironment`'s own `reference()`/
`listKeys()` usage, which predates this PBI) short-circuits what-if's nested-deployment analysis
for the whole template. `validate` (full ARM template validation, not affected by this
limitation) was used instead and is the authoritative check.

## Deployment (blocked)

```
az deployment group create --resource-group rg-tmx-agent-platform-dev \
  --template-file ops/bicep/main.bicep --parameters ops/bicep/parameters/dev.bicepparam
```
Result: **Failed**, twice (once with `functionAppPlanSkuName=Y1`, once with `B1`), both with
`SubscriptionIsOverQuotaForSku` on `Microsoft.Web/serverFarms`
(`Current Limit (Total VMs): 0`). Confirmed subscription-wide via
`GET .../providers/Microsoft.Web/locations/{region}/usages` returning **0 entries** for
eastus2, eastus, westus2, and centralus — this subscription has never been granted any
`Microsoft.Web` App Service compute quota. See `decisions.md` for the required follow-up.

No other resource in the deployment failed or was modified destructively — the only other
change `what-if`/`validate` surfaced was a benign, pre-existing ARM normalization
(`Microsoft.Insights/components` gains `Flow_Type`/`Request_Source` properties on any redeploy,
unrelated to this PBI's changes) on the existing `appi-tmxap-dev` resource.

## Live end-to-end validation (Mode A / Mode B) — not performed

Both `CLAIMS_WORKFLOW_PROVIDER` modes require an actually-deployed, HTTP-reachable Function App.
Mode A (`inprocess`, the default) is exercised by the full pytest regression above (the Claims
E2E flow already covers it). Mode B (`durable`) requires the blocked deployment above and could
not be run — tracked as the immediate follow-up in `decisions.md`.

## PBI-06-01A — root cause investigation and `P0v4` workaround attempt (2026-08-10)

All commands below were actually executed in this session against the real
`rg-tmx-agent-platform-dev` resource group / subscription `4112e852-665c-44c4-ad9d-67432600fc65`.

```
az deployment group show --resource-group rg-tmx-agent-platform-dev --name <Y1-deployment>
az deployment group show --resource-group rg-tmx-agent-platform-dev --name <B1-deployment>
az deployment operation group list --resource-group rg-tmx-agent-platform-dev --name <each>
```
Result: complete nested ARM error chain retrieved for both prior failed deployments —
`DeploymentFailed` → `InvalidTemplateDeployment` → `ValidationForResourceFailed` →
`SubscriptionIsOverQuotaForSku` on `Microsoft.Web/serverFarms`, byte-identical for `Y1` and `B1`.

```
az rest --method get --url ".../providers/Microsoft.Web/locations/{region}/usages?api-version=2024-11-01"
```
Result (live, `eastus2`/`eastus`): `limit: 0` for every classic SKU family (`Y1`, `B1`, `F1`,
`D1`, `S1`-`S3`, `P1`-`P3`, `I1v2`-`I3v2`, `P1v2`-`P3v2`, `P0v3`-`P3v3`, `EP1`-`EP3`,
`WS1`-`WS3`) and for the `"Total Regional VMs"` (`*`) aggregate; `limit: 30` for `P0v4`-`P3v4`/
`P1mv4`-`P5mv4` (Premium v4) specifically. `westus2`/`centralus`/`southcentralus`: aggregate `*`
also `0`. `Microsoft.Web` provider registration: `Registered`.

```
az bicep build --file ops/bicep/main.bicep --stdout
```
Result: compiles cleanly with `P0v4` added to `appServicePlanSkuName`'s `@allowed` list (5
references to `PremiumV4`/`P0v4` confirmed present in the compiled template).

```
az deployment group validate --resource-group rg-tmx-agent-platform-dev \
  --template-file ops/bicep/main.bicep --parameters ops/bicep/parameters/dev.bicepparam
```
Result: **`provisioningState: "Succeeded"`** with `functionAppPlanSkuName=P0v4` — full ARM
template validation passed (this check does not simulate the real-time `serverFarms` quota
preflight, which only runs at `create`).

```
az deployment group create --resource-group rg-tmx-agent-platform-dev \
  --name pbi-06-01a-p0v4-20260809201107 \
  --template-file ops/bicep/main.bicep --parameters ops/bicep/parameters/dev.bicepparam
```
Result: **Failed** — `Microsoft.Web/serverFarms` preflight, `SubscriptionIsOverQuotaForSku`,
`Current Limit (Total VMs): 0`, tracking ID `5d016539-06a2-4ad6-967a-1081b6e78309`. Identical
failure mode to `Y1`/`B1` despite the usages catalog showing `P0v4: limit=30`.

```
az resource list --resource-group rg-tmx-agent-platform-dev --query "[?contains(type,'Microsoft.Web')]"
```
Result: **empty** — zero `Microsoft.Web` resources exist in the resource group. ARM preflight
rejected before any resource was created; nothing was left partially provisioned, nothing to
roll back. No Broker/Commercial/frontend/networking/RBAC/production resource was read, modified,
or touched by this investigation.

**Conclusion:** the `P0v4` workaround does not unblock deployment — this subscription has zero
deployable `Microsoft.Web`/App Service quota for any SKU, in every region checked. Live
validation (Mode A/Mode B/correlation ID/claim+adjuster assignment through the deployed Function
App) was explicitly conditioned on a successful deployment and correctly not attempted, since
deployment failed. See `decisions.md` D-07 and ADR-0003 for full narrative and evidence.

## PBI-06-01 (P0v4 redeploy retry + live Mode A validation) — 2026-08-10, later session

At the user's explicit request, repeated the P0v4 deployment attempt and, since it failed again,
substituted a real live validation of Mode A (the only mode not blocked by the Function App
non-deployment) against the already-deployed DEV Container App.

```
az rest --method get --url ".../providers/Microsoft.Web/locations/eastus2/usages?api-version=2024-11-01"
```
Result: unchanged from the prior session — `Y1: limit=0`, `B1: limit=0`, `P0v4: limit=30`,
`*` (Total Regional VMs): `limit=0`.

```
az bicep build --file ops/bicep/main.bicep --stdout
az deployment group validate --resource-group rg-tmx-agent-platform-dev \
  --template-file ops/bicep/main.bicep --parameters ops/bicep/parameters/dev.bicepparam
```
Result: both succeeded (`provisioningState: "Succeeded"`).

```
az deployment group create --resource-group rg-tmx-agent-platform-dev \
  --name pbi-06-01-p0v4-retry-20260809202401 \
  --template-file ops/bicep/main.bicep --parameters ops/bicep/parameters/dev.bicepparam
```
Result: **Failed** — `Microsoft.Web/serverFarms` preflight, `SubscriptionIsOverQuotaForSku`,
`Current Limit (Total VMs): 0`, tracking ID `508ca40c-9d59-4f05-8aed-217bab653672` (a different
tracking ID than the prior attempt — a genuinely independent evaluation, same result).

```
az resource list --resource-group rg-tmx-agent-platform-dev --query "[?contains(type,'Microsoft.Web')]"
```
Result: **empty** — zero `Microsoft.Web` resources exist. Nothing provisioned, nothing to roll
back.

### Live Mode A (in-process) validation — real HTTP calls against the deployed DEV API

Since the Function App does not exist, Mode B/Function-App-health/Durable orchestration could
not be validated (no such resource to check). Mode A does not depend on the Function App at all
(it is the pre-existing in-process path), so it was validated live against the real, already
running `ca-tmxap-dev-api` Container App (`https://ca-tmxap-dev-api.bluemushroom-e2f74836.eastus2.azurecontainerapps.io`):

| Turn | Message (summary) | Result |
|---|---|---|
| 1 | "report a claim for policy SYN-POL-0001" | HTTP 200, routed to `ClaimsAgent`, `policy_lookup` tool call succeeded (`status: active`, `holder_name: Synthetic Claimant One`), `X-Correlation-ID: pbi-06-01-p0v4-modeA-smoke-1` echoed back |
| 2–7 | incident date/location/description, contact info, injuries/third parties, drivability | HTTP 200 each turn, state incrementally filled |
| 8 | vehicle drivable confirmation | HTTP 200 — `validate_policy_status`/`payment_status`/`coverage_lookup` all reflected in state: `policy_active: true`, `payment_current: true`, `coverage_type: "Cobertura amplia"`, `coverage_limit: 250000.0`, `coverage_deductible: 5000.0`; state → `confirming` |
| 9 | "Yes, please register the claim." | HTTP 200 — `claim_registration` → `claim_reference: SYN-CLM-2026-0003`; `adjuster_assignment` → `adjuster_assigned: "Synthetic Adjuster Rivera"`; state → `adjuster_assigned` |
| 10 | correlation-ID-only check | HTTP 200, `X-Correlation-ID: pbi-06-01-p0v4-corr-check-final` echoed back unchanged |

Every one of the six mandatory/stretch Claims Tools (`policy_lookup`, `validate_policy_status`,
`payment_status`, `coverage_lookup`, `claim_registration`, `adjuster_assignment`) executed
successfully with correct synthetic data through the real, live DEV deployment, and correlation
ID propagation was confirmed on every turn. This is Mode A only — Mode B (Durable, via the
Function App) remains unvalidated because the Function App was never successfully deployed.

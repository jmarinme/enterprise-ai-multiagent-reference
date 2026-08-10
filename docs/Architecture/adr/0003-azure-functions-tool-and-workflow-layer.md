# ADR-0003: Azure Functions Tool Layer + Durable Functions Workflow Engine (Claims vertical slice)

## Status

Accepted — 2026-08-09/10 (PBI-06-01). Amended 2026-08-10 (PBI-06-01A) to document the `P0v4`
DEV hosting workaround. Implemented for Claims only; Broker and Commercial Intake remain on the
pre-existing in-process implementation, compatible with this architecture and migratable in a
future PBI without further abstraction changes.

## Context

`reports/review/01_architecture_review.md` Finding A-03 identified a real, undocumented
architecture drift: CLAUDE.md §4.1/§4.2/§5 specify Azure Functions as the Tool Layer and
Durable Functions as the Claims workflow engine, but the implementation ran every Tool
in-process inside the FastAPI app and the Claims intake flow as a synchronous, in-process,
dict-dispatched state machine. The review's own recommendation (§2a) was: "this should be
reconciled with an ADR (either adopt Functions for Tools, or amend §4.2/§5 to reflect the
in-process design as the accepted pattern) before this platform is treated as architecture
ground truth."

The PBI-06-01 prompt that initiated this work referenced "ADR-002 and ADR-007" as though they
already documented this decision. Neither exists: `docs/Architecture/adr/` contains only
ADR-0001 (networking posture) and ADR-0002 (VNet/Private Endpoints hardening), and neither
covers the Tool/Workflow layer. This ADR is the actual, first reconciliation of Finding A-03 —
not an update to a pre-existing decision.

This PBI adopts Functions for Tools (does not amend CLAUDE.md to accept the in-process design),
per CLAUDE.md §1's instruction to propose the smallest compliant correction toward the
documented architecture, and per the review's own assessment that the in-process design, while
functionally reasonable for a synthetic demo, is a real gap against the project's stated stack.

## Decision

### Provider abstractions (Domain Agents never know where a Tool/workflow executes)

- **`ToolProvider`** (`src/core/tool_provider/`): a Protocol matching the existing
  `ToolExecutor.execute(request) -> ToolResult` shape exactly.
  - `InProcessToolProvider` (default, `TOOL_PROVIDER=inprocess`): thin delegation wrapper around
    the pre-existing `ToolExecutor`/`ToolRegistry` — zero duplicated logic, zero behavior change.
  - `AzureFunctionToolProvider` (`TOOL_PROVIDER=azure_functions`): calls
    `POST {AZURE_FUNCTIONS_BASE_URL}/api/tools/{tool_name}`, the exact same
    `ToolRequest`/`ToolResult` JSON contract, over HTTP. Never raises — every failure mode
    (timeout, connection error, non-2xx) normalizes into `ToolResult(success=False, error=...)`.
- **`ClaimsWorkflowProvider`** (`src/core/workflow_provider/`): a Protocol for the Claims
  post-confirmation transaction (claim registration + adjuster assignment).
  - `InProcessClaimsWorkflowProvider` (default, `CLAIMS_WORKFLOW_PROVIDER=inprocess`): runs the
    same two Tool calls the pre-existing `_handle_ready_to_register`/`_handle_registered`
    handlers already made, now behind the seam, through an injected `ToolProvider`.
  - `DurableClaimsWorkflowProvider` (`CLAIMS_WORKFLOW_PROVIDER=durable`): starts
    `claims_workflow_orchestrator` via its HTTP starter endpoint and polls
    `statusQueryGetUri` until `Completed`/`Failed`/`Terminated`.

Both are selected by configuration (`src/config/settings.py`: `ToolProviderSettings`,
`ClaimsWorkflowSettings`) via factories (`src/core/tool_provider/factory.py`,
`src/core/workflow_provider/factory.py`), wired in `apps/api/src/api/dependencies.py` — the
same pattern every other provider (`LLMProvider`, `ConversationRepository`, `KnowledgeProvider`)
already uses in this codebase. `ClaimsAgent`'s constructor parameter is still named
`tool_executor` (not renamed to avoid an unrelated breaking change across 6 existing test
files) but its type annotation is now `ToolProvider` — a concrete `ToolExecutor` satisfies it
structurally (Python Protocols), so every existing caller/test needed zero changes.

### Azure Functions Tool Layer (`ops/functions/claims_tools/function_app.py`)

One HTTP-triggered route, `POST /api/tools/{tool_name}`, executing exactly the Claims Agent's
approved Tool set: `policy_lookup`, `payment_status`, `coverage_lookup` (mandatory per PBI-06-01
Phase 3) plus `claim_registration`, `adjuster_assignment` (low-risk stretch goal, included).
`customer_lookup` was deliberately NOT migrated — out of PBI-06-01's mandatory/stretch scope.

No business logic is duplicated: the Function App imports and executes the same
`src.tools.executor.ToolExecutor` / `src.services.tools.*` classes the in-process path uses,
vendored into the deployment package at build time (`ops/functions/claims_tools/build.ps1`
copies repo-root `src/` alongside `function_app.py`) — mirroring `apps/api/Dockerfile`'s own
repo-root `src/` COPY convention (CLAUDE.md §6: one reusable `src/` library).

### Durable Functions Workflow Engine (same `function_app.py`)

`claims_workflow_orchestrator` runs the exact flow PBI-06-01 specifies:
`policy_lookup -> payment_status -> coverage_lookup -> claim_registration ->
adjuster_assignment -> return result`, each step a Durable activity function calling the same
`ToolExecutor`. Started only via `claims_workflow_starter`
(`POST /api/orchestrators/claims_workflow_orchestrator`), which `DurableClaimsWorkflowProvider`
calls only after `ClaimsAgent`'s state machine reaches `READY_TO_REGISTER` — i.e., only after
the caller has explicitly confirmed (`src/agents/claims/workflow.py`:
`_handle_ready_to_register_workflow`). No conversational state (which fields are still missing,
the confirmation summary, language, etc.) is ever passed to or held by the orchestrator — only
the already-collected, already-confirmed fields (`ClaimsWorkflowInput`).

### Safe fallback (Phase 5)

`TOOL_PROVIDER=inprocess` and `CLAIMS_WORKFLOW_PROVIDER=inprocess` are the defaults everywhere
(`src/config/settings.py`, `ops/bicep/parameters/dev.bicepparam`). With both at their defaults,
`ClaimsAgent` behaves identically to before this PBI — verified by the full pre-existing 64-test
Claims suite passing unchanged, plus the full 577-test repository suite. Flipping either
setting is a config-only change (Container App env var), never a code redeploy.

### Function-level HTTP auth (documented DEV simplification)

`ops/functions/claims_tools/function_app.py` uses `AuthLevel.ANONYMOUS`, not function-key auth.
A Consumption/Basic-plan Function App's runtime keys are only generated after its code has
synced post-deployment — key-based auth cannot be wired inside the same Bicep deployment that
creates the app without a fragile manual post-deploy step. `AzureFunctionToolProvider` and
`DurableClaimsWorkflowProvider` already support key auth
(`AZURE_FUNCTIONS_USE_KEY`/`DURABLE_FUNCTIONS_USE_KEY`, resolved via the existing
`SecretProvider`/Key Vault abstraction) for when a future PBI wires real access control (Easy
Auth, or APIM + Managed Identity in front of the Function App) — this PBI ships the anonymous
default with that follow-up explicitly named, not silently deferred.

### Infrastructure (Phase 6) — additive only

- `ops/bicep/modules/storage-account.bicep`: new Storage Account (`AzureWebJobsStorage` +
  Durable Task Hub). `allowSharedKeyAccess: false` — identity-based access only, via the
  platform's existing shared user-assigned Managed Identity (reused, not a second identity),
  granted Storage Blob Data Owner / Queue Data Contributor / Table Data Contributor scoped to
  this one storage account.
- `ops/bicep/modules/function-app.bicep`: new App Service Plan + Function App
  (`kind: functionapp,linux`, Python 3.12), reusing the same shared Managed Identity and the
  existing Key Vault-backed Application Insights connection string secret
  (`appinsights-connection-string`) — no new identity, no new Key Vault, no new Log
  Analytics/App Insights resource.
- **Reused, untouched**: Container Apps (API/Web), Cosmos DB, Azure AI Search, Azure OpenAI,
  Key Vault, networking (`enablePrivateNetworking` unchanged), Container Registry.
- **App Service Plan SKU: `dev.bicepparam` currently sets `P0v4` (Premium v4)** — attempted as a
  workaround for the `Y1`/`B1` quota block; **it also failed** (see "`P0v4` investigated..."
  below for the full root-cause evidence). `functionAppPlanSkuName` (`main.bicep`,
  `ops/bicep/modules/function-app.bicep`) accepts `Y1` (architectural default), `B1`, or `P0v4`
  so this environment can move to whichever value is actually deployable without any module
  change once the subscription's App Service quota is granted. See `docs/sprint_06/decisions.md`.

### `P0v4` investigated as a DEV hosting workaround — did not unblock deployment (PBI-06-01A)

PBI-06-01A investigated why the PBI-06-01 deployment above failed, found a candidate DEV
workaround (`P0v4`), added Bicep support for it (`ops/bicep/modules/function-app.bicep`,
`main.bicep`, `dev.bicepparam`), and tested it with a real deployment attempt. The candidate
did **not** work — the subscription has zero deployable App Service quota, full stop, regardless
of SKU. `functionAppPlanSkuName=P0v4` remains available as a parameterized option (harmless,
additive, and ready to use the moment real quota exists — see the tier-mapping/Always-On changes
below), but DEV is deployed in `inprocess` mode today exactly as before this investigation.

- **`Y1`/`B1` quota is confirmed `0`** in this subscription (`4112e852-665c-44c4-ad9d-67432600fc65`,
  `tokiomarine.com.mx` tenant). Two real `az deployment group create` attempts against
  `rg-tmx-agent-platform-dev` (`Y1`, then `B1`) both failed identically at ARM preflight:
  `Microsoft.Web/serverFarms` → `SubscriptionIsOverQuotaForSku`, `Current Limit (Total VMs): 0`.
  A live `GET .../providers/Microsoft.Web/locations/{region}/usages` (api-version `2024-11-01`)
  confirms `limit: 0` for every classic App Service compute family (`F1`, `D1`, `B1`-`B3`,
  `S1`-`S3`, `P1`-`P3`, `Y1`, `I1v2`-`I3v2`, `Iv41`-`Iv43`, `P1v2`-`P3v2`, `P0v3`-`P3v3`,
  `EP1`-`EP3`, `WS1`-`WS3`) and for the aggregate `"Total Regional VMs"` line (`*`), across
  `eastus2`, `eastus`, `westus2`, `centralus`, and `southcentralus`.
- **`P0v4`'s advertised quota (`limit: 30`) does NOT reflect real, enforceable capacity for this
  subscription — confirmed by an actual deployment attempt, not just the catalog query.** The
  `Microsoft.Web/locations/{region}/usages` catalog lists `limit: 30` for `P0v4`-`P3v4` and
  `P1mv4`-`P5mv4` (Premium v4) in `eastus2`/`eastus`, separately from the `0`-limit
  `"Total Regional VMs"` (`*`) aggregate that blocks `Y1`/`B1`. This looked like a viable,
  quota-driven DEV workaround and `P0v4` is a real, ARM-recognized SKU/tier
  (`Microsoft.Web/geoRegions?sku=PremiumV4` lists `East US 2` as an available region for tier
  `PremiumV4`). **A real `az deployment group create` with `functionAppPlanSkuName=P0v4` against
  `rg-tmx-agent-platform-dev` was attempted (PBI-06-01A, 2026-08-10) and failed with the
  byte-identical `SubscriptionIsOverQuotaForSku` error as `Y1`/`B1`** (`Microsoft.Web/serverFarms`
  preflight, `Current Limit (Total VMs): 0`, `Current Usage: 0`, tracking ID
  `5d016539-06a2-4ad6-967a-1081b6e78309`). Re-querying the usages catalog immediately afterward
  still shows `P0v4: limit=30` unchanged — the catalog's per-SKU `limit` field is descriptive
  (what the SKU family could support if quota existed) and does not represent an actual
  entitlement; the single `"Total Regional VMs"` (`*`) aggregate at `0` is what ARM's real
  `Microsoft.Web/serverFarms` creation preflight actually enforces, and it gates **every** App
  Service Plan SKU in this subscription without exception. No `Microsoft.Web` resource
  (App Service Plan or Function App) was created by this attempt — `az resource list` against
  `rg-tmx-agent-platform-dev` confirms zero `Microsoft.Web` resources exist; ARM preflight
  rejects before any resource is provisioned, so there is nothing to clean up.
  **Conclusion: there is no SKU-selection workaround for this subscription's App Service
  quota — it is a genuine `0` for the entire `Microsoft.Web` compute resource type in every
  region checked, and only an Azure Support quota-increase grant resolves it.**
- **`P0v4` is a Dedicated App Service hosting plan for Azure Functions**, not a serverless
  Consumption or Elastic Premium plan — it is the newest generation (v4) of the same "Dedicated
  (App Service) plan" hosting model `B1` already uses (`kind: functionapp,linux`,
  `reserved: true`), with a fixed-capacity, always-on VM rather than pay-per-execution or
  burst/pre-warmed-instance billing. `ops/bicep/modules/function-app.bicep` maps
  `appServicePlanSkuName == 'P0v4'` to `sku.tier: 'PremiumV4'` and sets `siteConfig.alwaysOn: true`
  for any non-`Y1` (i.e. Dedicated-family) plan — Dedicated plans, unlike Consumption, idle the
  host down without it, which would starve the Durable Task Hub's ability to make forward
  progress on a running orchestration.
- **`P0v4` was scoped and would only ever have been a DEV-only implementation workaround, never
  the preferred production hosting recommendation** — even had it deployed successfully, Premium
  v4 Dedicated is not a statement about the architecturally preferred Functions hosting model for
  this platform (see the production reevaluation list below). Since it did not deploy either,
  this point is now moot for the current subscription state, but the Bicep support and this
  framing stay documented for whenever quota allows a retry.
- **A second, independent deployment attempt (2026-08-10, same day, later session) reproduced the
  identical failure** — `az deployment group create` with `P0v4` against
  `rg-tmx-agent-platform-dev` failed again with `SubscriptionIsOverQuotaForSku`
  (`Current Limit (Total VMs): 0`, tracking ID `508ca40c-9d59-4f05-8aed-217bab653672`), and a
  fresh usages requery immediately before the attempt still showed `P0v4: limit=30`. Two
  independent real attempts, minutes to hours apart, both blocked identically — this is not a
  transient error. `az resource list` confirmed zero `Microsoft.Web` resources exist afterward.
  Given the Function App was not deployed, **Mode B (Durable) live validation, Function App
  health, and Durable orchestration could not be validated** — no such resource exists to check.
  **Mode A (in-process) live validation was performed instead**, directly against the
  already-deployed DEV API Container App (`ca-tmxap-dev-api...azurecontainerapps.io`, running
  since PBI-03-05/PBI-06-01, unaffected by this Function App blocker since Mode A never calls
  Azure Functions): a real multi-turn `/chat` conversation using synthetic policy `SYN-POL-0001`
  exercised `policy_lookup`, `validate_policy_status`, `payment_status`/`get_payment_status`, and
  `coverage_lookup` (all returned correct synthetic data — active policy, current payment,
  "Cobertura amplia" coverage), then `claim_registration` (produced `SYN-CLM-2026-0003`) and
  `adjuster_assignment` (assigned "Synthetic Adjuster Rivera") — the complete Claims Tool set.
  `X-Correlation-ID` sent on each request was echoed back unchanged on every response, confirming
  correlation ID propagation through the live Supervisor → ClaimsAgent → Tool path. This
  reconfirms Mode A is fully functional and was never affected by the Function App quota
  block — only Mode B (which requires the undeployed Function App) remains unvalidated.
- **Production should reevaluate hosting model by workload and available quota at that time** —
  candidates, in order of fit for a serverless Tool Layer + Durable Functions workflow engine:
  - **Flex Consumption (`FC1`)** — the current-generation serverless Functions plan (per-execution
    billing, fast cold start, VNet integration without a Dedicated plan's fixed cost); the
    closest production analogue to this platform's original `Y1` intent and worth evaluating
    first once its own quota is confirmed.
  - **Elastic Premium (`EP1`-`EP3`)** — serverless with pre-warmed instances (no cold start) and
    VNet integration; a fit if Flex Consumption's execution model doesn't cover a specific
    production requirement (e.g. longer execution limits).
  - **Consumption (`Y1`)** — the original architectural default; viable once genuine Dynamic/
    Consumption quota is granted for a low-to-moderate, bursty synthetic workload.
  - **Dedicated (any generation, including `P0v4`)** — last choice for this workload: fixed cost,
    always-on, no scale-to-zero: appropriate only if a future requirement (e.g. VNet integration
    unavailable on Consumption/Elastic Premium in the chosen region, or a need for reserved
    capacity) specifically calls for it.
  This reevaluation is a follow-up, not part of PBI-06-01/PBI-06-01A — tracked under "Review
  triggers" below.

### Observability (Phase 7)

Every Tool/activity call logs `claims_tool_activity_start`/`_end` or
`claims_activity_start`/`_end` with `tool_name`/`activity`, `correlation_id`, and `success` —
`X-Correlation-ID` (or the JSON body's `correlation_id`) is read at the HTTP boundary and
threaded through every activity and the orchestrator's own input, so a single correlation ID is
traceable API → Supervisor → ClaimsAgent → (Durable Workflow →) Azure Functions → response, same
as the pre-existing in-process path. No conversation content, prompt text, or business PII is
logged — only tool name, activity name, correlation ID, and a boolean success flag (CLAUDE.md
§10).

## Alternatives considered

- **Amend CLAUDE.md §4.2/§4.5 to accept the in-process design instead.** Rejected: the review
  explicitly offered this as the alternative resolution, but CLAUDE.md's own principle #4 ("Tool
  Calling for business action... deterministic, versioned, testable, and auditable") and the
  academic project's stated second goal (a *reusable reference* for real enterprise builds)
  favor demonstrating the documented serverless pattern over retroactively lowering the bar to
  match what happened to get built first.
- **Migrate all three domain agents' Tools/workflows in one PBI.** Rejected per the PBI's own
  explicit instruction: implement the complete architecture, but migrate only Claims as the
  first fully-migrated vertical slice, leaving Broker/Commercial on the existing in-process
  implementation (still architecture-compliant — they call the same `ToolExecutor` any
  `InProcessToolProvider` wraps).
- **Function-key or Easy Auth from day one.** Rejected for this PBI given the Bicep
  same-deployment key-generation ordering problem above; named as a follow-up, not silently
  dropped.

## Consequences

- Positive: Finding A-03 is resolved for the Claims vertical — Azure Functions and Durable
  Functions are real, running (pending the quota grant), tested code, not aspirational
  documentation. The provider-abstraction pattern is directly reusable for Broker/Commercial in
  a future PBI with no further framework changes.
- Negative / accepted risk: two providers (`ToolProvider`, `ClaimsWorkflowProvider`) add a small
  amount of indirection for a synthetic, low-volume academic demo where the in-process path
  alone would have sufficed functionally — accepted because it is exactly what CLAUDE.md's
  stack inventory requires and the review flagged as missing.
- Follow-up (not yet done, tracked below): Broker/Commercial Tool migration; remaining Claims
  Tools (`customer_lookup`) behind the Function App; function-key/Easy Auth/APIM access control;
  an Azure App Service quota increase request for this subscription — required regardless of
  SKU, since `Y1`, `B1`, and `P0v4` all failed identically (PBI-06-01A); a production
  hosting-model reevaluation (Flex Consumption / Elastic Premium / Consumption) once quota
  exists, since `P0v4` was never more than a DEV workaround candidate and did not even work as
  that.

## Review triggers

- Before promoting `TOOL_PROVIDER=azure_functions`/`CLAIMS_WORKFLOW_PROVIDER=durable` to any
  environment beyond DEV.
- Before migrating Broker or Commercial Intake onto these same abstractions.
- If the Azure App Service quota grant lands and `Y1` Consumption becomes viable — revisit
  `functionAppPlanSkuName` back to its architectural default.
- Before this platform (or a derived one) is deployed to any environment beyond DEV — `P0v4` is
  an explicit DEV-only workaround; production must reevaluate hosting model (Flex Consumption /
  Elastic Premium / Consumption) against the workload and whatever quota is available at that
  time, not inherit `P0v4` by default.

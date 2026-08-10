# Sprint 06 — Decisions and Deviations

## D-01: The PBI prompt's "ADR-002/ADR-007" references did not match the repository

The PBI-06-01 instructions referred to aligning "with ADR-002 and ADR-007" as though these
already documented the Tool/Workflow layer decision. `docs/Architecture/adr/` contains exactly
two ADRs: `0001-networking-posture-and-vnet-deferral.md` and
`0002-vnet-private-endpoints-hardening.md` — both about networking, neither about Tools or
workflows. Per CLAUDE.md §1 ("If code or a sprint instruction conflicts with the architecture
document, stop, report the conflict, and propose the smallest compliant correction"), this was
flagged at the start of the session and resolved by writing the actual first ADR for this
decision: `docs/Architecture/adr/0003-azure-functions-tool-and-workflow-layer.md`.

## D-02: `ClaimsAgent`'s `tool_executor` constructor parameter was not renamed

`ClaimsAgent.__init__`'s `tool_executor` parameter now types as `ToolProvider`, not
`ToolExecutor`. The parameter name itself was kept (not renamed to `tool_provider`) because six
existing test files construct `ClaimsAgent(tool_executor=...)` by keyword, and Python Protocols
are structural — a concrete `ToolExecutor` already satisfies `ToolProvider` without any
adapter. Renaming would have been a purely cosmetic, unrelated breaking change against CLAUDE.md
§7 ("smallest viable change", "preserve public contracts whenever possible"). The internal
`advance_claims_intake()` function's own parameter *was* renamed (`tool_executor` →
`tool_provider`) because its only caller is `ClaimsAgent` itself and its test callers all pass
it positionally, so the rename was zero-risk and improves clarity where it actually matters.

## D-03: Function-level HTTP auth deferred to `ANONYMOUS` for this PBI

See ADR-0003's "Function-level HTTP auth" section. Azure Functions key-based auth cannot be
wired inside the same Bicep deployment that creates a fresh Function App (keys generate only
after code sync, which happens in a separate deployment step). `AZURE_FUNCTIONS_USE_KEY`/
`DURABLE_FUNCTIONS_USE_KEY` settings and the `SecretProvider`-based key resolution already exist
in `src/core/tool_provider/azure_function.py`/`src/core/workflow_provider/durable.py` for a
future PBI to wire once a real access-control mechanism (Easy Auth, or APIM + Managed Identity)
is chosen — not silently dropped, named explicitly as a follow-up.

## D-04: App Service Plan SKU changed from `Y1` (Consumption) to `B1` (Basic) in `dev.bicepparam`

A real `az deployment group create` against `rg-tmx-agent-platform-dev` failed twice:

1. `functionAppPlanSkuName=Y1` (Consumption, the architectural default for a serverless Tool
   Layer): `SubscriptionIsOverQuotaForSku`, `Current Limit (Total VMs): 0`.
2. `functionAppPlanSkuName=B1` (Basic, a fixed-cost always-on tier, tried as a quota-safe
   fallback since `az vm list-usage --location eastus2` showed 10 available vCPUs on the
   "Standard Dv2 Family"): **identical failure**, also `Current Limit (Total VMs): 0`.

Root cause confirmed via `GET
https://management.azure.com/subscriptions/{id}/providers/Microsoft.Web/locations/{region}/usages?api-version=2023-01-01`:
this endpoint returned **0 entries** (not 0/10 — literally no quota line items at all) for
`eastus2`, `eastus`, `westus2`, and `centralus`. This subscription
(`tokiomarine.com.mx` tenant, Pay-As-You-Go) has never been granted any `Microsoft.Web` App
Service compute quota in any region checked — this is unrelated to `Microsoft.Compute` VM quota
(which does show availability) and unrelated to SKU choice; it blocks **every** App Service
Plan tier.

**Decision**: `functionAppPlanSkuName` (`ops/bicep/main.bicep`,
`ops/bicep/modules/function-app.bicep`) is parameterized with `Y1` as the module's documented
architectural default and `B1` as an explicit, allowed fallback — `dev.bicepparam` currently
sets `B1` only because it is what this session attempted next; **the deployment still failed
with `B1` for the same subscription-wide reason**, so `dev.bicepparam`'s `B1` value does not by
itself unblock deployment. Actual deployment requires the subscription owner to request an
Azure App Service quota increase (the error message names the exact ask: "New Limit that you
should request... 1") via an Azure Support ticket — outside this session's authorization
(the SAFETY OVERRIDE explicitly restricts autonomous action to creating the DEV Function
App/Storage Account and deploying to DEV; filing a subscription-level support/quota request is
neither of those).

**Impact**: PBI-06-01 closes as **COMPLETE WITH CONDITIONS** (see PBI summary) — every
verifiable-without-a-live-endpoint acceptance criterion is met (abstractions, Function App code
correctness confirmed via direct smoke tests, `az deployment group validate` succeeded, full
regression green); actual deployment and Mode A/Mode B live validation are blocked pending the
quota grant and are the immediate next action once it lands.

## D-05: Only `customer_lookup` was excluded from the Function App's Tool set

PBI-06-01 Phase 3 mandated `policy_lookup`/`payment_status`/`coverage_lookup` and named
`claim_registration`/`assign_adjuster` (implemented here as the existing `adjuster_assignment`
tool name — see D-06) as a low-risk stretch goal. `customer_lookup` (used earlier in the Claims
flow, before policy validation) was left in-process — not mandatory, not named as a stretch
goal, and migrating it would have widened this PBI's scope without a corresponding requirement.

## D-07: PBI-06-01A — root-caused the quota block precisely, then tested and disproved a `P0v4` DEV workaround

**Investigation (no code/infra changes).** Re-examined the PBI-06-01 `SubscriptionIsOverQuotaForSku`
failure with the complete nested ARM error chain (`az deployment group show` /
`deployment operation group list` for both the `Y1` and `B1` deployment attempts) and a live
requery of `Microsoft.Web/locations/{region}/usages` (the `2023-01-01` api-version used in
PBI-06-01 now returns HTTP 405; `2024-11-01` is current). Confirmed `Microsoft.Web` provider
registration is `Registered`, Bicep/`validate` are not the cause, storage provisioning succeeds,
and the block is region-independent (`eastus2`, `eastus`, `westus2`, `centralus`,
`southcentralus` all show `0` on the `"Total Regional VMs"` aggregate). New finding versus
PBI-06-01's evidence: the usages catalog lists non-zero `limit: 30` for Premium v4 (`P0v4`-`P3v4`,
`P1mv4`-`P5mv4`) specifically, distinct from every other SKU family's `0`.

**Workaround attempt (approved by the user for this DEV environment only).** Added `P0v4` as a
third `@allowed` value to `appServicePlanSkuName`
(`ops/bicep/modules/function-app.bicep`, `ops/bicep/main.bicep`), mapped it to `sku.tier:
'PremiumV4'`, added `siteConfig.alwaysOn: true` for any non-`Y1` (Dedicated-family) plan — Always
On is required on Dedicated plans so the host isn't idled between requests, which would starve
the Durable Task Hub's ability to progress a running orchestration — and set
`dev.bicepparam`'s `functionAppPlanSkuName = 'P0v4'`. `az bicep build` and
`az deployment group validate` both succeeded against `rg-tmx-agent-platform-dev`.

**Result: `az deployment group create` with `P0v4` also failed**, at the identical
`Microsoft.Web/serverFarms` preflight step, with the byte-identical `SubscriptionIsOverQuotaForSku`
message (`Current Limit (Total VMs): 0`, tracking ID `5d016539-06a2-4ad6-967a-1081b6e78309`) as
`Y1`/`B1`. Re-querying the usages catalog immediately afterward still shows `P0v4: limit=30`
unchanged — that field is descriptive of what the SKU family could theoretically support, not an
actual entitlement; the single `0`-value `"Total Regional VMs"` aggregate is what ARM's real
`Microsoft.Web/serverFarms` creation preflight enforces, and it blocks every SKU without
exception. `az resource list --resource-group rg-tmx-agent-platform-dev` confirms zero
`Microsoft.Web` resources exist — ARM preflight rejects before any resource is created, so
nothing was left to clean up, and no Broker/Commercial/frontend/networking/RBAC/production
resource was touched.

**Decision:** `dev.bicepparam` keeps `functionAppPlanSkuName = 'P0v4'` (matches the D-04
precedent of leaving `B1` set even though it didn't unblock deployment either) — the Bicep
support is harmless, additive, and ready to use without further module changes the moment this
subscription is granted real `Microsoft.Web` quota on any family. **There is no SKU-selection
workaround available**; only an Azure Support quota-increase request resolves this. Live
validation (Mode A/Mode B/correlation ID/claim+adjuster through the deployed Function App) was
correctly not attempted — it was explicitly conditioned on a successful deployment, which did not
occur. ADR-0003 updated with the full evidence chain and a corrected conclusion (initial framing
of `P0v4` as a working "DEV hosting workaround" was revised after the real deployment attempt
disproved it — see the ADR's own note on this).

**Repeat attempt, same day, later session:** re-run at the user's explicit request
(`az deployment group create` with `P0v4`, deployment name
`pbi-06-01-p0v4-retry-20260809202401`) — failed identically (`SubscriptionIsOverQuotaForSku`,
tracking ID `508ca40c-9d59-4f05-8aed-217bab653672`), confirmed via a fresh
`Microsoft.Web` usages requery immediately beforehand (`P0v4: limit=30` unchanged) and
`az resource list` immediately after (zero `Microsoft.Web` resources). Two independent real
attempts now agree: this is a stable, subscription-wide `0`-quota condition, not a transient
fault. Since the Function App still does not exist, Mode B/Function-App-health/Durable
orchestration remain unvalidatable. **Mode A (in-process) live validation was performed instead**
directly against the already-deployed DEV API Container App — a real multi-turn `/chat`
conversation (synthetic policy `SYN-POL-0001`) exercised the complete Claims Tool set
(`policy_lookup`, `validate_policy_status`, `payment_status`, `coverage_lookup`,
`claim_registration` → `SYN-CLM-2026-0003`, `adjuster_assignment` → "Synthetic Adjuster Rivera")
with `X-Correlation-ID` echoed correctly on every turn. See ADR-0003 and `validation.md` for the
full transcript summary.

## D-06: Kept the existing `adjuster_assignment` Tool name, not `assign_adjuster`

CLAUDE.md §4.2's minimum reference Tool list names `assign_adjuster`; the Tool actually
implemented since Sprint 02 (`src/services/tools/adjuster_assignment_tool.py`) is named
`adjuster_assignment`. This naming drift predates this PBI and is out of scope to rename here
(renaming a working, tested Tool purely for naming-convention alignment is exactly the kind of
unrelated change CLAUDE.md §7 asks to avoid) — the Function App reuses the existing name
unchanged, consistent with every other Tool it exposes.

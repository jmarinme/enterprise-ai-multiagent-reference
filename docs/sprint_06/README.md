# Sprint 06 — Serverless Architecture Alignment

## Objective

Resolve Architecture Review Finding A-03 (`reports/review/01_architecture_review.md`):
CLAUDE.md §4.1/§4.2/§5 specify Azure Functions as the Tool Layer and Durable Functions as the
Claims workflow engine; the implementation ran everything in-process. Introduce reusable
`ToolProvider`/`ClaimsWorkflowProvider` abstractions, implement the Azure Functions Tool Layer +
Durable Functions Claims workflow, and migrate Claims as the first fully-migrated vertical
slice — without migrating Broker or Commercial Intake, and without breaking the existing
in-process implementation.

## Scope

- [x] PBI-06-01: Serverless Architecture Alignment (Azure Functions + Durable Functions).
- [x] PBI-06-01A: Azure Deployment Root Cause Investigation + `P0v4` DEV workaround attempt.

## Out of scope

- Broker Services / Commercial Intake Tool or workflow migration (remain in-process, still
  architecture-compliant — future PBIs).
- Migrating `customer_lookup` to the Function App (not in PBI-06-01's mandatory/stretch list).
- Function-key/Easy Auth/API Management access control for the Function App (documented
  follow-up — see ADR-0003).
- Entra ID, Redis, AKS/Kubernetes, another agent framework, another database (unchanged from
  every prior sprint's exclusions).

## Deliverables

- [x] PBI-06-01: `ToolProvider`/`ClaimsWorkflowProvider` abstractions, Azure Functions Tool
      Layer, Durable Functions Claims workflow, Claims vertical slice migrated, safe in-process
      fallback preserved, Bicep for the new Function App + Storage Account, ADR-0003.
- [x] PBI-06-01A: complete nested-ARM-error root cause investigation, `P0v4` DEV hosting
      workaround implemented and tested (failed — no SKU-selection workaround exists for this
      subscription's quota), ADR-0003 amended.

## Acceptance criteria

See `decisions.md` and `validation.md` for the full, evidence-backed accounting against
PBI-06-01's own stop-condition list.

## Dependencies

- Sprint 02's Claims Tool framework (`src/tools/*`, `src/services/tools/*`) — this PBI adds a
  provider seam in front of it, replacing none of its logic.
- `reports/review/01_architecture_review.md` Finding A-03 — the review this PBI resolves.

## Risks

See `decisions.md` — principally the Azure subscription's App Service quota blocker.

## Deliverable Log

<!-- Append entries. Do not remove previous entries. -->

PBI-06-01: `ToolProvider`/`ClaimsWorkflowProvider` abstractions (`src/core/tool_provider/`,
`src/core/workflow_provider/`), Azure Functions Tool Layer + Durable Functions Claims workflow
(`ops/functions/claims_tools/`), Claims vertical slice migrated (`src/agents/claims_agent.py`,
`src/agents/claims/workflow.py`), safe `inprocess` fallback verified (full 577-test regression
green), Bicep for Function App + Storage Account (`ops/bicep/modules/function-app.bicep`,
`storage-account.bicep`), ADR-0003. Bicep validated (`az deployment group validate`:
`Succeeded`) but **not deployed** — the subscription reported `SubscriptionIsOverQuotaForSku`
(0 App Service quota, confirmed across 4 regions) for both `Y1` and `B1` — 2026-08-09/10.
Evidence: `validation.md`, `decisions.md`, `evidence/`.

PBI-06-01A: root-caused the quota block with the complete nested ARM error chain and a live
`Microsoft.Web` usages requery — found `P0v4` (Premium v4) reporting non-zero catalog quota
(`limit: 30`) unlike every other SKU. Added `P0v4` as a DEV-only hosting option
(`ops/bicep/modules/function-app.bicep`, `main.bicep`, `dev.bicepparam`, incl. `alwaysOn` for
Dedicated plans), validated, and tested it with one real deployment attempt — **it also failed**,
byte-identical `SubscriptionIsOverQuotaForSku`, proving the catalog's per-SKU `limit` field is
descriptive, not an actual entitlement, and that this subscription has zero deployable
`Microsoft.Web` quota for any SKU. No resource was created (confirmed via `az resource list`);
live Mode A/B validation was correctly not attempted since it was conditioned on a successful
deployment — 2026-08-10. Evidence: `validation.md`, `decisions.md` (D-07), ADR-0003.

## Sprint validation

See `validation.md`. Final regression (2026-08-09/10): backend 577 passed/2 skipped (551 + 26
new provider/workflow tests), ruff clean, mypy clean (`apps/api/src`, `src`), Bicep build clean,
`az deployment group validate` succeeded. Azure deployment blocked by subscription App Service
quota — see `decisions.md`. PBI-06-01A (2026-08-10) re-confirmed the block with a second real
`az deployment group create` attempt using `P0v4` — also failed, `SubscriptionIsOverQuotaForSku`
— proving the block is subscription-wide across every SKU, not `Y1`/`B1`-specific.

## Sprint retrospective

The provider-abstraction pattern (`ToolProvider`/`ClaimsWorkflowProvider`, structural Protocols
matching the pre-existing `ToolExecutor` shape) let the entire Claims migration land with zero
changes to the 64 pre-existing Claims tests and zero changes to Broker/Commercial — the seam was
genuinely additive. The Azure App Service quota blocker was outside this PBI's control and is
the reason PBI-06-01 closes as COMPLETE WITH CONDITIONS rather than COMPLETE: everything
verifiable without a live Azure Functions endpoint (unit tests, direct HTTP-handler and
Durable-activity smoke tests, `az deployment group validate`) passed; live end-to-end validation
through an actually-deployed Function App could not be performed and is the immediate follow-up
once quota is granted.

PBI-06-01A's most useful result was negative: the `Microsoft.Web` usages catalog's per-SKU
`limit` field looked like real, actionable evidence of available quota (`P0v4: limit=30`) but
turned out to be descriptive, not an entitlement — only a genuine `az deployment group create`
attempt against the real subscription revealed that. This is worth remembering for any future
quota investigation on this or any subscription: trust the `create`-time preflight result, not
the usages catalog's `limit` field, as the authoritative signal.

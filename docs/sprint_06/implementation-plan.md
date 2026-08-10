# Sprint 06 — Implementation Plan

## PBI-06-01: Serverless Architecture Alignment

### Discovery (read before any code change)

- `reports/review/01_architecture_review.md` Finding A-03 — the drift being resolved.
- `docs/Architecture/adr/0001-*`, `0002-*` — confirmed neither covers the Tool/Workflow layer;
  the PBI prompt's references to "ADR-002/ADR-007" as pre-existing ground truth did not match
  the repository (see `decisions.md`).
- `src/tools/{executor,registry,protocol,models}.py` — the existing Tool framework this PBI
  fronts with a provider seam, never duplicates.
- `src/agents/claims_agent.py`, `src/agents/claims/{workflow,state}.py` — the conversation state
  machine this PBI must not move into Durable Functions.
- `apps/api/src/api/dependencies.py` — the one composition root every new provider factory is
  wired into, matching the existing `@lru_cache` singleton pattern.
- `ops/bicep/main.bicep` + `modules/*.bicep` — existing resource/tag/naming/RBAC conventions
  reused for the new Storage Account + Function App modules.

### Design

- `ToolProvider` Protocol (`src/core/tool_provider/protocol.py`) matches
  `ToolExecutor.execute(request) -> ToolResult` exactly — a structural, not nominal, contract.
  `InProcessToolProvider` wraps `ToolExecutor`; `AzureFunctionToolProvider` calls the Function
  App over HTTP with the identical JSON contract.
- `ClaimsWorkflowProvider` Protocol (`src/core/workflow_provider/protocol.py`) — `run(input) ->
  ClaimsWorkflowResult`. `InProcessClaimsWorkflowProvider` replays the pre-existing
  registration+adjuster Tool calls through an injected `ToolProvider`.
  `DurableClaimsWorkflowProvider` starts/polls a Durable Functions orchestration.
- Both selected via `src/config/settings.py` (`ToolProviderSettings`, `ClaimsWorkflowSettings`)
  and `src/core/*/factory.py`, matching `src.llm.factory`/`src.rag.factory`'s existing
  lazy-import, default-safe pattern.
- `src/agents/claims/workflow.py`: `advance_claims_intake` gains an optional
  `workflow_provider` parameter (default `None`). When set, `READY_TO_REGISTER` is handled by a
  new `_handle_ready_to_register_workflow` instead of the default
  `_handle_ready_to_register`/`_handle_registered` pair — producing identical notice text so the
  two modes are conversationally indistinguishable.

### Build order actually followed

1. `ToolProvider` abstraction + tests.
2. `ClaimsWorkflowProvider` abstraction + tests.
3. Rewire `ClaimsAgent`/`workflow.py` + `dependencies.py`; full regression run (551 passed
   unchanged) before touching infrastructure.
4. Azure Functions app (`ops/functions/claims_tools/function_app.py`): HTTP Tool Layer +
   Durable orchestrator/activities, reusing vendored `src/` (build.ps1), smoke-tested directly
   (no Azure Functions Core Tools available in this environment — see `validation.md`).
5. Bicep (`storage-account.bicep`, `function-app.bicep`), wired additively into `main.bicep`;
   `az bicep build` + `az deployment group validate` against the real DEV resource group.
6. New unit tests for both provider frameworks (26 tests) + full regression (577 passed).
7. Deployment attempt — blocked by subscription App Service quota (see `decisions.md`).
8. Documentation (this sprint folder, ADR-0003).

### Explicitly not done in this PBI

- Broker/Commercial migration.
- `customer_lookup` Function.
- Function-key/Easy Auth/APIM.
- Live Azure deployment/validation (blocked — see `decisions.md`).

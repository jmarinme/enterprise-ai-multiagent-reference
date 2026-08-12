# 00 — Project Inventory

> **Note on output location:** Written to `./review/` per this review's own instructions. A
> prior, independent review already exists at `reports/review/` (same six-file structure,
> earlier snapshot of this codebase, before PBI-06 through PBI-09). This review is a **fresh,
> current-state assessment** — it re-verifies every claim against the code as it exists today
> rather than assuming the prior review still holds, and calls out where things have changed.

## 1. What this repository is

TMX Enterprise AI Reference Platform — an **academic reference implementation** (CLAUDE.md §1)
of a corporate insurance multi-agent platform: a Supervisor Agent routes messages to one of three
domain agents (Claims, Broker Services, Commercial Intake), each using deterministic, typed Tools
(never the LLM directly) for every business fact or action, over an optional RAG layer and a
Cosmos DB conversation store, on Azure. Explicitly **not** an approved TMX production
architecture; synthetic data only (CLAUDE.md §1/§2).

A real Azure DEV environment (`rg-tmx-agent-platform-dev`) is live and has been deployed and
validated multiple times, most recently for this review's own immediate predecessor PBI
(PBI-09-01, conversational intelligence + live conversational validation), confirmed via direct
`az` CLI inspection during this review (see §7).

## 2. Repository scale (measured, `git ls-files`, this review)

| Metric | Value | Prior review (`reports/review/00_...`) | Delta |
|---|---|---|---|
| Tracked files | 441 | 363 | +78 |
| Python files (`*.py`) | 239 | 201 | +38 |
| TypeScript/TSX files | 24 | 24 | 0 |
| Combined LOC (py+ts+tsx) | 24,410 | 20,187 | +4,223 |
| Test files (`test_*.py` under `tests/`) | 93 | 76 | +17 |
| `tests/e2e/` real test files | 1 (`test_load.py`) | 0 | +1 |
| `tests/conversational/` real test files | 3 | 0 | +3 |
| ADRs | 11 (as of PBI-12-04; 3 at this table's original snapshot) | 2 | +1 since original snapshot (`0003-...`); +8 more since, most recently [ADR-0011](../docs/Architecture/adr/0011-react-pattern-for-tool-orchestrated-reasoning.md) (ReAct pattern for Tool-orchestrated reasoning), preceded by [ADR-0010](../docs/Architecture/adr/0010-enterprise-authentication-entra-id.md) (Microsoft Entra ID authentication) |
| Bicep modules | 17 | 15 | +2 (`function-app.bicep`, `storage-account.bicep`, `monitor-alerts.bicep` — net +3 shown as +2 due to a rename/consolidation not investigated further) |
| Sprints with a logged `README.md` | 9 (`sprint_00`–`sprint_09`) | 6 | +3 |

The growth is consistent with real, documented delivery, not scope creep: `docs/sprint_06`
through `docs/sprint_09` cover serverless architecture alignment, CI/CD, architecture-review
remediation, and this review's own immediate predecessor (conversation intelligence).

## 3. Tech stack — claimed (CLAUDE.md §5) vs. observed, re-verified

| Layer | CLAUDE.md claim | Observed now | Change since prior review |
|---|---|---|---|
| Backend API | Python 3.12, FastAPI, Pydantic | `apps/api/pyproject.toml`: `fastapi>=0.115,<1`, `pydantic>=2.7,<3` | Unchanged |
| Frontend | React, TypeScript | React 18.3, TS 5.5, Vite 5.4, Vitest 2.0 (`apps/web/package.json`) | Unchanged |
| LLM platform | Azure OpenAI / Azure AI Foundry | `AzureOpenAIProvider` (production), `MockLLMProvider` (tests), `OllamaLLMProvider` (local dev) — all behind `LLMProvider` Protocol, now with retry+circuit-breaker resilience (`src/core/resilience/`) | **Improved**: resilience wrapping added (was a HIGH/MEDIUM finding before) |
| Conversation store | Azure Cosmos DB | `CosmosConversationRepository` (Managed Identity, `disableLocalAuth: true`) + `InMemoryConversationRepository`, resilience-wrapped | **Improved**: resilience wrapping added |
| Document storage | Azure Blob Storage | **Still not implemented.** Knowledge docs remain Markdown under `configs/knowledge_base/` | Unchanged gap |
| RAG retrieval | Azure AI Search, optional | `AzureAISearchProvider` (service provisioned, still no index populated, `KNOWLEDGE_PROVIDER=local` by default), resilience-wrapped | Unchanged provisioning state; resilience added |
| Deterministic Tools | Azure Functions | **Still runs in-process** by default (`TOOL_PROVIDER=inprocess`, confirmed live on the DEV Container App). Azure Functions code now genuinely **exists** (`ops/functions/claims_tools/`) and is deployable behind `deployServerlessToolLayer` (default `false`), documented in ADR-0003 | **Materially improved**: the drift is now a deliberate, ADR-documented, feature-flagged choice — not an unexplained gap — but the functions are still not the default runtime path |
| Long-running workflows | Azure Durable Functions | `ClaimsWorkflowProvider` abstraction exists (`src/core/workflow_provider/`); in-process by default (`CLAIMS_WORKFLOW_PROVIDER=inprocess`, confirmed live) | **Improved**: a genuine provider abstraction now exists where before there was none; still not the default runtime path |
| Container runtime | Azure Container Apps | 2 apps live in DEV (`ca-tmxap-dev-api`, `ca-tmxap-dev-web`), confirmed via `az containerapp show` during this review | Unchanged |
| Registry | Azure Container Registry | `acrtmxapdevl3fgxt`, confirmed live, new API image tag present from this session's own deployment | Unchanged |
| Secrets | Azure Key Vault | `kv-tmxap-dev-l3fgxt` provisioned; `EnvironmentSecretProvider` (default) / `AzureKeyVaultSecretProvider` (opt-in) | Unchanged |
| Authentication | Microsoft Entra ID | **Implemented and live in DEV** (PBI-11-01 through PBI-11-01D). `apps/api/src/api/auth/` validates signature/expiry/audience/issuer on every request via MSAL Browser/React (OAuth2 Authorization Code + PKCE) on the frontend; identity is `f"{tid}:{oid}"`, never a client-supplied `userId`. See [ADR-0010](../docs/Architecture/adr/0010-enterprise-authentication-entra-id.md). | **Resolved — formerly the single largest gap; now closed and regression-tested** (`review/02_security_review.md` §3b, `review/04_risk_register.md` RISK-025/026) |
| IaC | Azure Bicep | 17 modules + `main.bicep` + 3 `.bicepparam` files | +2 modules net (function-app, storage-account, monitor-alerts) |
| CI/CD | Azure DevOps Pipelines | `azure-pipelines.yml`, now with a real `SecurityScan` stage (pip-audit, detect-secrets, npm audit) and a `ContainerBuildValidation` stage for feature branches | **Improved**: SCA/secret scanning added (was a MEDIUM gap before) |
| Observability | OpenTelemetry, App Insights, Azure Monitor, Log Analytics | App Insights + Log Analytics provisioned; structured logging + correlation-ID propagation; **3 metric alerts + 1 action group now provisioned** (`monitor-alerts.bicep`, confirmed live via `az resource list`). OpenTelemetry SDK still not present | **Improved**: alerting added (was a MEDIUM/operational gap); OTel itself still absent |
| Backend quality | Ruff, mypy, pytest | Confirmed, enforced in CI | Unchanged |
| Local runtime | Docker Compose | Unchanged | Unchanged |

**Still explicitly and correctly absent** (per CLAUDE.md §5's "do not add" list): AKS/Kubernetes
manifests (`ops/k8s/` still `.gitkeep`-only), Helm, Terraform, Redis, a second agent framework, a
second database technology.

## 4. Configuration and environment files (re-reviewed)

| File | Notes | Change |
|---|---|---|
| `.env.example` | All placeholders empty, no secret values | Unchanged |
| `.gitignore` | Excludes `.env*` (keeps `!.env.example`), `*.pem`/`*.key`/`*.pfx`, `secrets/`, generated Bicep JSON | Unchanged |
| `docker-compose.yml` | API + Web | Unchanged |
| `apps/api/Dockerfile` | `python:3.12-slim`, repo-root context, **still no `USER` directive** (runs as root) | Unchanged gap |
| `apps/web/Dockerfile` | `node:20-alpine`, **still `npm run preview` as the production command** (Vite's own docs say this is not production-intended), **still no `USER` directive** | Unchanged gap |
| `azure-pipelines.yml` | Now includes a real `SecurityScan` stage (pip-audit with one documented, justified ignored CVE — `PYSEC-2026-1845`, a dev-only `pytest` finding never shipped in the container; detect-secrets; npm audit) and a `ContainerBuildValidation` stage for `feat/*`/`fix/*`/`review/*` branches | **Improved** since prior review |
| `ops/bicep/main.bicep` + 17 modules + 3 `.bicepparam` | `deployServerlessToolLayer` param (default `false`) now gates Function App/Storage Account/App Service Plan; confirmed live — no `Microsoft.Web/*` resources exist in the resource group today | **Improved**: was previously undocumented drift, now a deliberate, reviewable, off-by-default flag |
| `pyproject.toml` (root) + `apps/api/pyproject.toml` | Range-pinned (`>=x,<y`), **still no lockfile** (no `poetry.lock`/`uv.lock`/`requirements.lock`) | Unchanged gap |
| `apps/web/package.json` + `package-lock.json` | React 18.3, TS 5.5; lockfile present | Unchanged |
| `.pre-commit-config.yaml` | **Still does not exist** | Unchanged gap |

No file examined contained a real-looking secret. The previously-flagged stray root file
(`tatus`) has been **removed** (confirmed absent via `git ls-files`).

## 5. Entry points

| Entry point | File |
|---|---|
| API (FastAPI) | `apps/api/src/main.py::create_app()` — mounts `health` (`/health`, `/ready`), `version`, `chat`, `conversations` routers, `CORSMiddleware`, `CorrelationIdMiddleware` |
| API composition root | `apps/api/src/api/dependencies.py` |
| Web (React) | `apps/web/src/main.tsx` / `App.tsx` |
| Azure Functions | `ops/functions/claims_tools/` — now exists, but not the default deployed/running path (`deployServerlessToolLayer=false`) |

## 6. Module map — unchanged in shape, extended in depth

The layered `apps/web → apps/api → src/supervisor → src/agents → src/tools/src/services/src/prompts/src/llm/src/rag/src/core → src/services/conversation_store, src/services/secret_store`
structure documented in the prior review still accurately describes the codebase. Two additions
since:

- `src/core/resilience/` (retry + circuit breaker) is now a shared dependency of every
  external-call provider (`AzureOpenAIProvider`, `AzureAISearchProvider`,
  `CosmosConversationRepository`).
- `src/core/tool_provider/` and `src/core/workflow_provider/` are new Protocol layers between
  each Agent and its concrete Tool/workflow execution, enabling the in-process/Azure-Functions
  split without changing Agent code (`docs/Architecture/adr/0003-...md`).
- `src/agents/shared/memory.py` and `src/agents/shared/summary.py` (new, PBI-09-01): a global,
  cross-agent conversation-memory value object, threaded through all three domain Agents via the
  same explicit-metadata-echo pattern every other per-agent state key already used.

## 7. Data persistence — re-verified, plus live confirmation

Same shape as the prior review (Cosmos for conversation history / synthetic in-memory Tool data /
Markdown knowledge base / Key Vault-or-env secrets). **New for this review**: the live DEV
Container App's actual environment configuration was inspected directly (`az containerapp show`)
during this session's own deployment — confirmed `CONVERSATION_STORE_PROVIDER=cosmos`,
`TOOL_PROVIDER=inprocess`, `CLAIMS_WORKFLOW_PROVIDER=inprocess`, `KNOWLEDGE_PROVIDER=local`,
`LLM_PROVIDER=azure_openai` (against a real `gpt-5-mini` deployment) are the actual running
values, not just documented intent.

No real customer, policy, claim, broker, or payment data exists anywhere — synthetic-data mandate
confirmed still honored (`src/services/tools/synthetic/provider.py`, unchanged naming/labeling
convention).

## 8. Documentation reviewed

All of the prior review's list, plus: `docs/sprint_06/`–`docs/sprint_09/` (READMEs read in full),
`docs/Architecture/adr/0003-azure-functions-tool-and-workflow-layer.md`, `reports/review/*`
(the prior review itself, read in full as baseline context for this one).

## 9. Files/areas not read (explicit scope limitations, same as prior review)

- `TMX_Enterprise_AI_Reference_Architecture_and_Delivery_Standard_V2.0.docx` — not opened
  (binary); relies on CLAUDE.md's own summary, same as the prior review.
- Individual `docs/sprint_NN/decisions.md`/`validation.md` files for sprints predating this
  review's own PBI-09 work were sampled via targeted `grep`, not read end-to-end; `sprint_09`'s
  own docs (this review's immediate predecessor) were read in full since they are directly
  relevant and current.
- `tests/unit/**` (now 93 files) sampled by directory/representative file + this session's own
  first-hand knowledge of the ones authored/modified in the immediately preceding PBIs, not read
  file-by-file exhaustively.
- `apps/web/node_modules/`, `.venv/`, `.mypy_cache/`, `.ruff_cache/` — correctly out of scope.
- Azure resources **were** queried live this time (`az account show`, `az resource list`,
  `az containerapp show`, `az containerapp revision list`, `az acr repository show-tags`) as a
  direct consequence of this session's own PBI-09-01 DEV deployment minutes earlier — this review
  is **not** purely static/offline the way the prior one was, for the resources touched by that
  deployment specifically. No new live query was performed beyond confirming the already-executed
  deployment's state.

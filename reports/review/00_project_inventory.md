# 00 — Project Inventory

> **Output location note:** This review's output was relocated from the generic `./review/`
> convention to `reports/review/` because CLAUDE.md §6 forbids creating a new top-level folder
> without approval, and `reports/` already exists as an approved top-level folder.

## 1. What this repository is

TMX Enterprise AI Reference Platform — an **academic reference implementation** (per
`CLAUDE.md` §1) of a corporate insurance multi-agent platform: Supervisor Agent + three domain
agents (Claims, Broker Services, Commercial Intake) over deterministic Tools, optional RAG, and
a Cosmos DB conversation store, built on Azure. It is explicitly **not** an approved TMX
production architecture and is required to use only synthetic data. This context (from
`CLAUDE.md`, already read in full) is treated as given, not re-discovered, throughout this
review.

The repository is unusually mature for an academic project: 6 sprints (`sprint_00`–`sprint_05`)
are fully logged with deliverable logs, decisions, and validation evidence, and a real Azure DEV
environment (`rg-tmx-agent-platform-dev`) has been deployed and live-validated multiple times
(see `docs/sprint_03/README.md`, `docs/sprint_04/README.md`).

## 2. Repository scale

Measured directly (`git ls-files`, run from repo root):

| Metric | Value |
|---|---|
| Tracked files (`git ls-files \| wc -l`) | 363 |
| Python files (`*.py`) | 201 |
| TypeScript/TSX files (`*.ts`/`*.tsx`) | 24 |
| Combined LOC (py + ts + tsx, `wc -l`) | 20,187 |
| Test files under `tests/` | 76 (66 under `tests/unit/`, 2 under `tests/integration/`, 0 real tests under `tests/e2e/` or `tests/conversational/` — both contain only `.gitkeep`) |
| Sprints with a closed/logged `README.md` | 6 (`sprint_00`–`sprint_05`) |
| ADRs | 2 (`docs/Architecture/adr/0001-...md`, `0002-...md`) |

## 3. Tech stack — claimed (CLAUDE.md §5) vs. observed

| Layer | CLAUDE.md claim | Observed | Drift |
|---|---|---|---|
| Backend API | Python 3.12, FastAPI, Pydantic | `apps/api/pyproject.toml`: `fastapi>=0.115,<1`, `pydantic>=2.7,<3`, `python_requires>=3.12` | None |
| Frontend | React, TypeScript | `apps/web/package.json`: React 18.3, TS 5.5, Vite 5.4, Vitest 2.0 | None |
| LLM platform | Azure OpenAI / Azure AI Foundry | `src/llm/azure_openai_provider.py` (production-shaped, Entra ID default) + `MockLLMProvider` (test default) + `OllamaLLMProvider` (local dev, added Sprint 03) | **Addition, not drift**: Ollama is a third, local-only provider layered on top of the required Mock/Azure OpenAI pair — reasonable, not in the CLAUDE.md stack table, not a violation of §5's "do not add another … framework" (it's a provider behind the existing `LLMProvider` Protocol) |
| Conversation store | Azure Cosmos DB for NoSQL | `src/services/conversation_store/`: `InMemoryConversationRepository` (default/tests) + `CosmosConversationRepository` (Managed Identity only, `disableLocalAuth: true`) | None |
| Document storage | Azure Blob Storage | **Not implemented.** No `src/services/*blob*` or Bicep storage-account module found | Real gap — Blob Storage is in CLAUDE.md §5 but knowledge documents are instead versioned under `configs/knowledge_base/` (Markdown), not Blob Storage |
| RAG retrieval | Azure AI Search, optional | `src/rag/`: `LocalKnowledgeProvider` (default) + `AzureAISearchProvider` (Managed Identity default); `ops/bicep/modules/ai-search.bicep` provisions the *service* only, no index deployed | None (documented — `KNOWLEDGE_PROVIDER` defaults to `local` because no index exists yet, see `docs/sprint_03/decisions.md`) |
| Deterministic Tools | Azure Functions | **Not implemented as Azure Functions.** All 14 Tools (`src/services/tools/*.py`) run in-process inside the API, invoked via `src/tools/executor.py` | Real drift from §5 — Tools are a clean, versioned, in-process abstraction (satisfying principle #4) but are not hosted in Azure Functions as §5 specifies. No Durable Functions exist either. |
| Long-running workflows | Azure Durable Functions | Not implemented; Claims intake is a synchronous, in-process state machine (`src/agents/claims/state.py`) | Drift from §4.1 ("Claims Agent... delegates long-running processes to Durable Functions") |
| Container runtime | Azure Container Apps | `ops/bicep/modules/container-app.bicep`, 2 apps deployed live in DEV | None |
| Registry | Azure Container Registry | `ops/bicep/modules/container-registry.bicep`, admin user disabled, AcrPull/AcrPush via Managed Identity | None |
| Secrets | Azure Key Vault | `ops/bicep/modules/key-vault.bicep` (RBAC-only) + `src/services/secret_store/` (`EnvironmentSecretProvider` default, `AzureKeyVaultSecretProvider` opt-in) | None |
| Workload identity | Managed Identity | Single shared user-assigned identity, used throughout | None |
| Authentication | Microsoft Entra ID | **Not implemented.** No token validation middleware anywhere in `apps/api/src/`; `userId` is a client-generated, unauthenticated value (`apps/web/src/utils/userId.ts`) | Documented, known, planned gap — see `docs/sprint_00/security-baseline.md` §7, `docs/sprint_04/decisions.md` (2026-08-08 entries). Not a surprise finding. |
| IaC | Azure Bicep | 15 `.bicep` files under `ops/bicep/modules/` + `main.bicep`, 3 `.bicepparam` files | None |
| CI/CD | Azure DevOps Pipelines | `azure-pipelines.yml`, 8 conceptual stages, real CD to DEV since Sprint 04 | None |
| Observability | OpenTelemetry, App Insights, Azure Monitor, Log Analytics | App Insights + Log Analytics provisioned in Bicep; structured JSON logging + correlation-ID propagation in code (`apps/api/src/observability/logging.py`, `apps/api/src/api/middleware/correlation_id.py`). **No OpenTelemetry SDK found** (`grep` for `opentelemetry` in `pyproject.toml`/`requirements` returned nothing) | Partial drift — App Insights/Log Analytics/structured logging are real; OpenTelemetry itself (the specific SDK named in §5) is not wired in |
| Backend quality | Ruff, mypy, pytest | Confirmed: `[tool.ruff]`/`[tool.mypy]` in both `pyproject.toml` files, `pytest` used throughout, run in CI | None |
| Local runtime | Docker Compose | `docker-compose.yml` present, API+Web, `host.docker.internal` wiring for local Ollama | None |

**Explicitly and correctly absent** (per CLAUDE.md §5's own "do not add" list, verified not present): AKS, Kubernetes manifests (`ops/k8s/` exists but is empty except `.gitkeep`, matching CLAUDE.md's "reserved for future use"), Helm, Terraform, Redis, a second agent framework (no LangGraph/AutoGen/CrewAI/Semantic Kernel import found anywhere), a second database technology.

## 4. Configuration and environment files reviewed

| File | Notes |
|---|---|
| `.env.example` | Present, all placeholders empty, no secret values. Documents `LLM_PROVIDER`, `CONVERSATION_STORE_PROVIDER`, `KNOWLEDGE_PROVIDER`, `SECRET_PROVIDER`, `CORS_ALLOWED_ORIGINS`, etc. |
| `.gitignore` | Explicitly excludes `.env`, `.env.*` (keeps `!.env.example`), `*.pem`, `*.key`, `*.pfx`, `secrets/`; also excludes `reports/*` (except `.gitkeep`) and `ops/bicep/**/*.json` (generated ARM templates) |
| `docker-compose.yml` | API + Web services; `extra_hosts: host.docker.internal:host-gateway` added in Sprint 03 for local Ollama |
| `apps/api/Dockerfile` | `python:3.12-slim`, repo-root build context (required since PBI-03-02), no `USER` directive (runs as root) |
| `apps/web/Dockerfile` | `node:20-alpine`, single-stage, production command is `npm run preview` (Vite's own docs: not intended for production), no `USER` directive |
| `azure-pipelines.yml` | Single YAML pipeline, 8 stages, real CD to DEV since PBI-04-01; reviewed in full (651 lines) |
| `ops/bicep/main.bicep` + 15 modules + 3 `.bicepparam` files | Reviewed for RBAC and networking posture (see `02_security_review.md` §3e) |
| `pyproject.toml` (root) | Domain library (`src/`) deps: `pydantic`, `pydantic-settings`, `pyyaml`, plus optional extras (`cosmos`, `keyvault`, `azureopenai`, `azuresearch`, `ollama`, `dev`). Version ranges (`>=x,<y`), no lockfile. |
| `apps/api/pyproject.toml` | Transport-layer deps: `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`. Same range-pinning style. |
| `apps/web/package.json` + `package-lock.json` | React 18.3, TypeScript 5.5, Vite 5.4, Vitest 2.0, ESLint 9. Lockfile present (npm). |

No file contained a real-looking secret (API key, password, connection string, private key). One stray, out-of-place tracked file was found at repo root: **`tatus`** — a plain-text dump of a `git diff`/`git status`-style command output (its content is a diff against `TMX_initialprompt_Sprint0.md`), almost certainly an accidental `git s... > tatus`-style redirect that got committed. It contains no secrets, but it is dead, meaningless content sitting at the repo root — flagged in `03_code_quality_review.md`.

## 5. Entry points

| Entry point | File |
|---|---|
| API (FastAPI) | `apps/api/src/main.py::create_app()` — mounts `health`, `version`, `chat`, `conversations` routers, `CORSMiddleware`, `CorrelationIdMiddleware` |
| API composition root | `apps/api/src/api/dependencies.py` — the only place concrete Agents/Tools/Providers are imported and wired (documented, deliberate pattern) |
| Web (React) | `apps/web/src/main.tsx` (not read in full; `App.tsx` is the real chat client) |
| Azure Functions | **None found.** No `function_app.py`/`host.json`/`function.json` anywhere — Tools run in-process in the API, not as Azure Functions, despite CLAUDE.md §5 listing Azure Functions as the deterministic-Tool host |

## 6. Module map and interconnection

```
apps/web/src        React chat client — calls POST /chat, GET /conversations[/{id}]
      |
apps/api/src         FastAPI transport layer (routes, DI composition root, CORS, correlation ID,
      |               structured logging) — imports src/* as a library (PYTHONPATH=/app in the
      |               Docker image, "src" prefix imports)
      v
src/supervisor/       SupervisorOrchestrator — depends only on Protocols (ConversationRepository,
      |               IntentResolver, AgentRegistry); zero references to concrete agents
      v
src/agents/           ClaimsAgent, BrokerAgent, CommercialIntakeAgent, FallbackAgent — each
      |               depends only on ToolExecutor, PromptManager, LLMProvider, (Claims only:
      |               KnowledgeRetriever, Grounder, ToolCallingOrchestrator) — never a concrete
      |               Tool/Prompt-provider/LLM-provider
      v
src/tools/, src/services/tools/, src/prompts/, src/llm/, src/rag/, src/core/tool_calling/
                      Framework layers (Protocol + concrete implementations), each with its own
                      typed contracts and exceptions
      v
src/services/conversation_store/, src/services/secret_store/
                      Cosmos DB / in-memory conversation persistence; Key Vault / env-var secrets
```

`src/domain/` holds shared contracts (`Conversation`, `Message`, Protocol definitions) imported
by both the persistence layer and the supervisor. `src/observability/` (root-level) is distinct
from `apps/api/src/observability/` (API-local structured logging + correlation-ID context var) —
a deliberate split documented in `src/supervisor/orchestrator.py`'s own docstring ("this is a
reusable src/ module; apps/api depends on src/, never the reverse").

## 7. Data persistence — real Azure wiring vs. synthetic/mock

| Layer | Default (local/tests) | Azure-backed alternative | Synthetic data source |
|---|---|---|---|
| Conversation history | `InMemoryConversationRepository` | `CosmosConversationRepository` (`src/services/conversation_store/cosmos.py`), Managed Identity only, `disableLocalAuth: true` | N/A (real user turns, but userId itself is synthetic/unauthenticated) |
| Business facts (policies, claims, brokers, commissions, customers, coverages) | N/A — always synthetic | N/A — no real business system exists | `src/services/tools/synthetic/provider.py`: small, explicitly-labeled fabricated records (`SYN-POL-*`, `SYN-BRK-*`, `CUS-SYN-*`, etc.) |
| Knowledge/RAG documents | `LocalKnowledgeProvider` over `configs/knowledge_base/*.md` | `AzureAISearchProvider` (service provisioned, **no index created/populated** — `KNOWLEDGE_PROVIDER` defaults to `local` in every environment) | 5 synthetic Markdown documents |
| Secrets | `EnvironmentSecretProvider` (env vars) | `AzureKeyVaultSecretProvider` (Managed Identity) | N/A |

No real customer, policy, claim, broker, or payment data exists anywhere in the repository —
consistent with CLAUDE.md §1/§2's synthetic-data mandate.

## 8. Documentation reviewed

- `README.md` (root)
- `CLAUDE.md` (full — supplied in this session's system context, treated as authoritative)
- `docs/sprint_00/README.md` through `docs/sprint_05/README.md` (all 6, in full)
- `docs/Architecture/adr/0001-networking-posture-and-vnet-deferral.md`,
  `0002-vnet-private-endpoints-hardening.md` (0001 read in full detail; 0002 referenced)
- `docs/sprint_00/security-baseline.md` (Entra ID scope-out, §7)
- `docs/sprint_04/decisions.md` (Entra ID restatement, conversation-history route decisions) —
  sampled via targeted `grep`, not read end-to-end
- Sprint `decisions.md`/`validation.md` files for sprints 01–03/05 were **not** read end-to-end
  (budget); the corresponding `README.md` Deliverable Logs — which restate each PBI's validation
  outcome in detail — were read in full instead and are cited throughout this review in their
  place. This is a scope limitation of this review, not a claim that those files were reviewed.

## 9. Files/areas not read (explicit scope limitations)

- `TMX_Enterprise_AI_Reference_Architecture_and_Delivery_Standard_V2.0.docx` (binary DOCX,
  primary architecture reference per CLAUDE.md §1) — not opened; this review relies on
  CLAUDE.md's own summary of it plus the sprint documentation trail.
- Individual `docs/sprint_NN/decisions.md` / `validation.md` files — sampled, not read in full,
  per the note above.
- `tests/unit/**` — sampled by directory/file listing and a handful of representative reads
  (`tests/unit/api/`), not every one of the 66 unit test files individually, per the task's own
  "sampling is fine for tests/" instruction.
- `apps/web/node_modules/`, `apps/api/.venv/`, `.mypy_cache/`, `.ruff_cache/` — build artifacts,
  correctly out of scope for a source review.
- No live Azure resource was queried or inspected as part of this review — this is a **static,
  offline code review only**. Every claim about the live DEV deployment's behavior in this
  report is drawn from the sprint documentation's own recorded evidence (`validation.md`
  entries, Deliverable Log summaries), not independently re-verified against the running
  service.

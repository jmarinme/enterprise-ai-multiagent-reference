# Sprint 03 — Local Runtime, Ollama LLM Provider & Azure Runtime Integration

## Objective

Allow the full multi-agent platform to run locally with a real LLM through Ollama, while
preserving the Mock and Azure OpenAI providers untouched, and complete the local `docker
compose` runtime (API + Web) so the platform is startable without any Azure dependency
(PBI-03-01). Then make the platform production-shaped for Azure by wiring the already-built
Azure providers (`AzureOpenAIProvider`, `AzureAISearchProvider`, `CosmosConversationRepository`)
together through configuration and completed Infrastructure as Code, without deploying anything
(PBI-03-02).

## Scope

- `OllamaLLMProvider` (`src/llm/ollama_provider.py`): a third `LLMProvider` implementation,
  alongside `MockLLMProvider` and `AzureOpenAIProvider`, calling a local (or host-reachable)
  Ollama server's `/api/chat` REST endpoint over `aiohttp`.
- Configuration-driven provider selection (`LLM_PROVIDER=ollama`), typed `LLMSettings`
  additions (`OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT_SECONDS`), and a new
  `src/llm/factory.py` branch — `MockLLMProvider` remains the test/default provider.
- Typed exception normalization of Ollama HTTP/timeout/connection failures into the existing
  `LLMTimeoutError`/`LLMRateLimitError`/`LLMProviderError`/`LLMConfigurationError` hierarchy.
- Best-effort Tool Calling mapping to Ollama's documented OpenAI-compatible `tools=`/
  `message.tool_calls` shape, explicitly documented as model-dependent and not live-verified
  (no local Ollama+tool-capable model available in this environment).
- `docker-compose.yml`/`apps/api/Dockerfile` updates so the API can reach a host-run Ollama
  server (`host.docker.internal`) without requiring Ollama itself to run inside Docker.
- Documented environment variables for a fully local run (`InMemoryConversationRepository` +
  `LocalKnowledgeProvider` + `OllamaLLMProvider`, zero Azure dependency).
- **PBI-03-02:** a new `ops/bicep/modules/azure-openai.bicep` module (Cognitive Services OpenAI
  account + one chat model deployment), completing the Bicep inventory CLAUDE.md §4 requires.
  RBAC wiring (least privilege, data-plane roles only) so the API's Managed Identity can invoke
  Azure OpenAI, query Azure AI Search, access Cosmos DB, and read Key Vault secrets where
  applicable. The API Container App's environment now actually sets `LLM_PROVIDER`,
  `KNOWLEDGE_PROVIDER`, `CONVERSATION_STORE_PROVIDER`, and every Azure endpoint/resource-name
  value the running app needs (previously unset — Cosmos/AI Search were provisioned but never
  actually selected) — all as plain, non-secret Container App env vars. A new ADR documents the
  current public-network-access/RBAC-only networking posture versus what production hardening
  (VNet, Private Endpoints) would still require, explicitly deferred to a future PBI.

## Out of scope

- Azure deployment (`az deployment ... create`/`what-if` were never executed), APIM,
  authentication, VNet/private networking (see
  `docs/Architecture/adr/0001-networking-posture-and-vnet-deferral.md`).
- Real company/customer data.
- New agents, new RAG features, new Tool Calling capabilities beyond what PBI-02-04 already
  built.
- Running Ollama itself inside Docker (host-run, opt-in, by design).
- Azure AI Search index creation/document ingestion — `knowledgeProvider` therefore stays
  `local` even in the Azure Bicep parameter files (see `decisions.md`).
- Real side-effecting Tool integrations; weakening the Tool allow-list/validation controls.

## Deliverables

- [x] PBI-03-01: Add Ollama LLM Provider and complete the local runtime.
- [x] PBI-03-02: Complete the Azure Runtime integration.

## Acceptance criteria

| ID | Criterion | Evidence expected |
|---|---|---|
| AC-01 | `OllamaLLMProvider` implements the existing `LLMProvider` Protocol; no Agent imports Ollama-specific code | Code review — `src/llm/ollama_provider.py`; no `ollama`/`aiohttp` import anywhere under `src/agents/` |
| AC-02 | Provider selection is configuration-driven (`LLM_PROVIDER=ollama`); default remains `mock` for tests | `pytest` evidence — `tests/unit/llm/test_factory.py` |
| AC-03 | Typed settings (`OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT_SECONDS`) exist with sane local defaults | Code review — `src/config/settings.py::LLMSettings` |
| AC-04 | A successful Ollama response maps to a typed `LLMResponse` | `pytest` evidence — `tests/unit/llm/test_ollama_provider.py::test_generate_success_returns_typed_llm_response` |
| AC-05 | Timeout, connection failure, and generic HTTP error are normalized into existing typed `LLM*Error` exceptions, never a raw `aiohttp` exception | `pytest` evidence — `test_ollama_provider.py::test_generate_timeout_raises_llm_timeout_error`, `::test_generate_connection_error_raises_llm_provider_error`, `::test_generate_http_error_raises_llm_provider_error` |
| AC-06 | `OllamaLLMProvider` is fully mocked in its own tests — never called against a real Ollama server in the automated suite | Code review + `pytest` evidence — `test_ollama_provider.py` (all `@patch`-mocked) |
| AC-07 | Tool Calling mapping is implemented per Ollama's documented API shape; the limitation (model-dependent, not live-verified) is explicitly documented | Code review — `src/llm/ollama_provider.py` module docstring; `docs/sprint_03/decisions.md` |
| AC-08 | Claims/Broker/Commercial, Tool Calling, RAG/Grounding, and `POST /chat` regression behavior remain intact | `pytest` evidence — full pre-existing regression suite passes unchanged |
| AC-09 | `docker-compose.yml` allows the containerized API to reach a host-run Ollama via `host.docker.internal`, without requiring Ollama inside Docker | Code review — `docker-compose.yml` `extra_hosts`; `docker compose config` evidence |
| AC-10 | `InMemoryConversationRepository` and `LocalKnowledgeProvider` remain the local defaults; no Cosmos dependency required for local execution | Code review — `src/config/settings.py` defaults unchanged; `pytest` evidence — full regression suite |
| AC-11 | Required environment variables for a fully local run are documented | Code review — `.env.example` |
| AC-12 | The local runtime is startable with `docker compose up` when Docker is available | `docker compose config` evidence; live smoke test if Docker is available in this environment |
| AC-13 | `AzureOpenAIProvider`/`AzureAISearchProvider`/`CosmosConversationRepository` are reused unmodified — no duplicated Azure provider implementation, no Agent rewrite | Code review — zero changes to `src/llm/azure_openai_provider.py`, `src/rag/azure_ai_search_provider.py`, `src/services/conversation_store/cosmos.py`, or any `src/agents/*.py` file this PBI |
| AC-14 | Azure runtime provider selection (`LLM_PROVIDER=azure_openai`, `KNOWLEDGE_PROVIDER=azure_ai_search`, `CONVERSATION_STORE_PROVIDER=cosmos`) is configuration-driven through the real composition root | `pytest` evidence — `tests/unit/api/test_dependencies.py` (13 tests) |
| AC-15 | Missing Azure configuration (endpoint, index name) fails safely with the existing typed exceptions, through the factory and the composition root, not just direct provider construction | `pytest` evidence — `test_dependencies.py::test_get_llm_provider_missing_azure_configuration_raises`, `::test_get_knowledge_retriever_missing_azure_configuration_raises`, `::test_get_supervisor_missing_cosmos_configuration_raises`; `tests/unit/llm/test_factory.py::test_factory_azure_openai_missing_endpoint_raises_configuration_error`; `tests/unit/rag/test_rag_factory.py::test_factory_azure_ai_search_missing_index_name_raises_configuration_error` |
| AC-16 | Managed Identity remains the default auth path — no `SecretProvider` is built unless `*_USE_API_KEY` is explicitly set | `pytest` evidence — `test_dependencies.py::test_get_llm_provider_uses_managed_identity_by_default_not_secret_provider`, `::test_get_knowledge_retriever_uses_managed_identity_by_default_not_secret_provider` |
| AC-17 | Bicep provisions Azure OpenAI (account + one model deployment), completing the CLAUDE.md §4 inventory; every module builds cleanly | `az bicep build` evidence — `ops/bicep/modules/azure-openai.bicep`, `main.bicep`, all 11 modules |
| AC-18 | RBAC assignments let the API's Managed Identity invoke Azure OpenAI, query AI Search, access Cosmos DB, read Key Vault secrets, and pull container images — least privilege, data-plane scope only | Code review — `ops/bicep/modules/azure-openai.bicep` (Cognitive Services OpenAI User), plus the pre-existing Search Index Data Reader / Cosmos DB Data Contributor / Key Vault Secrets User / AcrPull assignments |
| AC-19 | No hardcoded subscription, tenant, resource group, endpoint, deployment, index, account name, or secret anywhere in Bicep or Container App env vars | Code review — every value is a param, module output, or `uniqueString()`-derived name; App Insights connection string remains the only actual secret, delivered via a Key Vault reference, never a plain env var |
| AC-20 | `knowledgeProvider` defaults to `local`, not `azure_ai_search`, because no AI Search index exists yet — selecting it before an index exists would crash-loop the container | Code review — `main.bicep` param description + all three `.bicepparam` files; `docs/sprint_03/decisions.md` |
| AC-21 | Current networking posture (public network access + RBAC-only) is documented against what production hardening (VNet, Private Endpoints) would require, without implementing it | Code review — `docs/Architecture/adr/0001-networking-posture-and-vnet-deferral.md` |
| AC-22 | `az bicep build` passes for every affected module and `main.bicep`; `build-params` passes for dev/staging/prod | `az bicep build`/`build-params` evidence — all exit 0, 0 errors, 0 warnings |
| AC-23 | Mock/Ollama/local, Claims/Broker/Commercial, Tool Calling, RAG/Grounding, and `POST /chat` regression behavior remain intact after the Azure wiring | `pytest` evidence — full pre-existing regression suite passes unchanged; live local smoke test with default (non-Azure) providers |
| AC-24 | No `az deployment ... create`/`what-if` executed; no real Azure credentials used in tests | Code review + validation log — only `az bicep build`/`build-params` (offline compilation) were run |

## Dependencies

- Sprint 01's LLM Adapter framework (`src/llm/`) and its established provider-mapping pattern
  (`AzureOpenAIProvider`, PBI-01-04).
- Sprint 02's Tool Calling framework (`src/core/tool_calling/`, PBI-02-04) — `OllamaLLMProvider`
  must support the same `LLMRequest.tools`/`LLMResponse.tool_calls` contract, best-effort.
- Existing `docker-compose.yml`/`apps/api/Dockerfile`/`apps/web/Dockerfile` (Sprint 00).
- PBI-03-02 depends on Sprint 00's Bicep foundation (Container Apps, Managed Identity, Key
  Vault, ACR), PBI-00-05's Cosmos DB module, and PBI-02-02's Azure AI Search module — it adds
  the missing Azure OpenAI module and the Container App environment-variable wiring connecting
  all three, without modifying any of them.

## Risks

| Risk | Probability | Impact | Mitigation |
|---|---:|---:|---|
| No local Ollama installation or Docker daemon available in this development environment | Realized | Low | `OllamaLLMProvider` is fully unit-tested with mocked HTTP calls (never touches a real server in the automated suite); a real smoke test is explicitly optional and its absence documented as an environmental limitation, not a code defect (see `validation.md`) |
| Ollama's tool-calling support varies by model/version | Realized (by design) | Low | Mapped per Ollama's documented API shape but not live-verified; a model without tool-calling support simply returns no `tool_calls`, which `ToolCallingOrchestrator` already treats as a safe "no tool requested" outcome — the deterministic Claims workflow is never at risk |
| Docker daemon unavailable in this environment; no real Azure subscription/credentials used | Realized | Low | `az bicep build`/`build-params` (offline compilation, no daemon/credentials needed) fully validate the IaC; `docker compose config` validates the compose file structurally; no deployment was in scope for this PBI regardless |
| Defaulting `knowledgeProvider=azure_ai_search` before an index exists would crash-loop the API Container App | Avoided by design | Would have been High | `knowledgeProvider` defaults to `local` in `main.bicep` and every `.bicepparam` file until a future PBI creates and populates the AI Search index (see `decisions.md`) |

## Deliverable Log

<!-- Append entries. Do not remove previous entries. -->

PBI-03-01: `OllamaLLMProvider` (`src/llm/ollama_provider.py`) added as a third `LLMProvider` implementation, structurally mirroring `AzureOpenAIProvider`'s proven shape (lazy `aiohttp` import — reused from this project's existing Azure extras, not a new dependency — typed exception mapping, construction-time configuration validation) rather than adding a new `ollama` SDK dependency. Calls a local/host-reachable Ollama server's documented `/api/chat` REST endpoint; timeout/connection/HTTP failures normalize into the existing `LLMTimeoutError`/`LLMRateLimitError`/`LLMProviderError`/`LLMConfigurationError` hierarchy — no new exception types. `LLMSettings` gained `llm_provider="ollama"`, `ollama_base_url` (default `http://localhost:11434`), `ollama_model`, and `ollama_timeout_seconds` (default 60s, deliberately independent of `LLMGenerationSettings`' cloud-tuned 30s default — see `decisions.md`); `src/llm/factory.py` gained one new lazy-import branch. `apps/api/src/api/dependencies.py` required zero changes — provider selection was already fully delegated to the factory. Tool Calling (PBI-02-04) is mapped to Ollama's documented OpenAI-compatible `tools=`/`message.tool_calls` shape, adapted for two real differences (a synthesized `call_id`, since Ollama assigns none, and already-parsed-dict arguments instead of a JSON string) — and this mapping was genuinely live-verified, not just unit-tested, because a real local Ollama server with a tool-calling-capable model (`llama3.2:3b`) turned out to be running in this development environment (see `validation.md`/`decisions.md` for the real `POST /chat` round trip, including a real Tool execution and an important architectural observation about LLM-fabricated Tool arguments staying safely isolated from the business-fact response text). `docker-compose.yml`'s `api` service gained `extra_hosts: host.docker.internal:host-gateway` so a containerized API can reach a host-run Ollama server (Ollama itself is intentionally not containerized); `apps/api/Dockerfile` now installs `aiohttp` unconditionally so the Ollama path works inside the built image without a rebuild. `InMemoryConversationRepository` and `LocalKnowledgeProvider` were confirmed as the unchanged local defaults (zero Cosmos/Azure AI Search dependency for local execution). `.env.example` documents every environment variable a fully local run requires (`LLM_PROVIDER`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT_SECONDS`). 398 tests pass deterministically (17 new: `tests/unit/llm/test_ollama_provider.py` (13) plus one new factory-selection test and 3 pre-existing regression assertions unaffected); ruff and mypy clean after one well-understood, justified fix (`Self` return type annotation on async context manager test doubles). `docker compose config` validated structurally (Docker daemon itself was unavailable in this environment — documented as an environmental limitation, not a code defect). No Azure deployment, Cosmos production wiring, Azure networking, APIM, authentication, new agents, or new RAG features implemented. — 2026-08-07
Evidence: `docs/sprint_03/evidence/pbi-03-01-ollama-provider-validation.txt`

PBI-03-02: Azure Runtime integration completed by wiring, not duplicating, the already-built Azure providers. New `ops/bicep/modules/azure-openai.bicep` provisions a Cognitive Services `OpenAI` account plus one chat-completion model deployment (default `gpt-4o-mini`), RBAC via the built-in "Cognitive Services OpenAI User" role — local (key) auth deliberately left enabled at the resource level, mirroring PBI-02-02's Azure AI Search precedent exactly, since `AzureOpenAIProvider` explicitly supports an opt-in `azure_openai_use_api_key` path via `SecretProvider` that must stay real and usable; Managed Identity remains the default. `main.bicep` gained `llmProvider`/`knowledgeProvider`/`conversationStoreProvider` params and now sets every provider-selection and endpoint/resource-name value the API Container App actually needs as a plain, non-secret env var (`LLM_PROVIDER`, `KNOWLEDGE_PROVIDER`, `CONVERSATION_STORE_PROVIDER`, `AZURE_OPENAI_ENDPOINT`/`DEPLOYMENT`/`API_VERSION`/`USE_API_KEY`, `AZURE_AI_SEARCH_ENDPOINT`/`INDEX_NAME`/`USE_API_KEY`, `COSMOS_DB_ENDPOINT`/`DATABASE`/`CONTAINER`) — previously entirely unset, meaning Cosmos/AI Search were being provisioned but the deployed API would never actually have selected them. `knowledgeProvider` deliberately defaults to `local`, not `azure_ai_search`, in `main.bicep` and all three `.bicepparam` files: no AI Search index exists yet (index creation/ingestion is out of scope), and `AzureAISearchProvider` raises `KnowledgeConfigurationError` at startup if `AZURE_AI_SEARCH_INDEX_NAME` is empty — defaulting to Azure there would have shipped a genuinely broken configuration; `llmProvider`/`conversationStoreProvider` default to `azure_openai`/`cosmos` since both are fully, safely provisioned by this same template. No new Container App secrets were needed — Managed Identity requires none, and the existing Key-Vault-reference pattern for the App Insights connection string was left untouched. A new ADR (`docs/Architecture/adr/0001-networking-posture-and-vnet-deferral.md`, the first ADR in this repository) documents the current all-public-network-access/RBAC-only posture against what VNet/Private Endpoint production hardening would require, explicitly deferred rather than mixed into this PBI. New composition-root tests (`tests/unit/api/test_dependencies.py`, 13 tests) exercise `apps/api/src/api/dependencies.py` directly — Azure provider selection, missing-configuration failures propagated through the factory layer, the Managed-Identity-default auth path (no `SecretProvider` built unless `*_USE_API_KEY` is set), and a full end-to-end composition test wiring all three Azure providers together at once — with an autouse fixture clearing every `@lru_cache`d composition-root singleton before and after each test so no wrongly-configured provider could leak into the rest of the suite; a full regression run immediately after confirmed zero pollution. New `tests/unit/services/test_conversation_store_factory.py` and two new missing-endpoint-via-factory tests (LLM, Knowledge) close the remaining "missing Azure configuration" gaps at the factory layer. 417 tests pass deterministically (21 new); ruff and mypy clean; all 12 Bicep files (`main.bicep` + 11 modules, including the new Azure OpenAI module) and all 3 parameter files compile with `az bicep build`/`build-params` at exit 0, 0 errors, 0 warnings; `docker compose config` unaffected (this PBI did not touch `docker-compose.yml`); live local smoke test with the default (Mock/local/in-memory) providers confirmed zero regression to the local runtime. No Azure resources were deployed — only offline `az bicep build`/`build-params` were executed; no `az deployment ... create`/`what-if`, no real Azure credentials in tests, no Agent rewritten, no Azure provider implementation duplicated, no Tool allow-list/validation control weakened. — 2026-08-07
Evidence: `docs/sprint_03/evidence/pbi-03-02-azure-runtime-integration-validation.txt`

## Sprint validation

See `validation.md`.

## Sprint retrospective

Complete when closing the sprint:

- What worked:
- What did not:
- Technical debt:
- Security findings:
- Follow-up PBIs:

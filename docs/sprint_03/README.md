# Sprint 03 — Local Runtime & Ollama LLM Provider

## Objective

Allow the full multi-agent platform to run locally with a real LLM through Ollama, while
preserving the Mock and Azure OpenAI providers untouched, and complete the local `docker
compose` runtime (API + Web) so the platform is startable without any Azure dependency.

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

## Out of scope

- Azure deployment, Cosmos production wiring, Azure networking, APIM, authentication.
- Real company/customer data.
- New agents, new RAG features, new Tool Calling capabilities beyond what PBI-02-04 already
  built (this PBI only extends which `LLMProvider` can drive it).
- Running Ollama itself inside Docker (host-run, opt-in, by design).

## Deliverables

- [x] PBI-03-01: Add Ollama LLM Provider and complete the local runtime.

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

## Dependencies

- Sprint 01's LLM Adapter framework (`src/llm/`) and its established provider-mapping pattern
  (`AzureOpenAIProvider`, PBI-01-04).
- Sprint 02's Tool Calling framework (`src/core/tool_calling/`, PBI-02-04) — `OllamaLLMProvider`
  must support the same `LLMRequest.tools`/`LLMResponse.tool_calls` contract, best-effort.
- Existing `docker-compose.yml`/`apps/api/Dockerfile`/`apps/web/Dockerfile` (Sprint 00).

## Risks

| Risk | Probability | Impact | Mitigation |
|---|---:|---:|---|
| No local Ollama installation or Docker daemon available in this development environment | Realized | Low | `OllamaLLMProvider` is fully unit-tested with mocked HTTP calls (never touches a real server in the automated suite); a real smoke test is explicitly optional and its absence documented as an environmental limitation, not a code defect (see `validation.md`) |
| Ollama's tool-calling support varies by model/version | Realized (by design) | Low | Mapped per Ollama's documented API shape but not live-verified; a model without tool-calling support simply returns no `tool_calls`, which `ToolCallingOrchestrator` already treats as a safe "no tool requested" outcome — the deterministic Claims workflow is never at risk |

## Deliverable Log

<!-- Append entries. Do not remove previous entries. -->

PBI-03-01: `OllamaLLMProvider` (`src/llm/ollama_provider.py`) added as a third `LLMProvider` implementation, structurally mirroring `AzureOpenAIProvider`'s proven shape (lazy `aiohttp` import — reused from this project's existing Azure extras, not a new dependency — typed exception mapping, construction-time configuration validation) rather than adding a new `ollama` SDK dependency. Calls a local/host-reachable Ollama server's documented `/api/chat` REST endpoint; timeout/connection/HTTP failures normalize into the existing `LLMTimeoutError`/`LLMRateLimitError`/`LLMProviderError`/`LLMConfigurationError` hierarchy — no new exception types. `LLMSettings` gained `llm_provider="ollama"`, `ollama_base_url` (default `http://localhost:11434`), `ollama_model`, and `ollama_timeout_seconds` (default 60s, deliberately independent of `LLMGenerationSettings`' cloud-tuned 30s default — see `decisions.md`); `src/llm/factory.py` gained one new lazy-import branch. `apps/api/src/api/dependencies.py` required zero changes — provider selection was already fully delegated to the factory. Tool Calling (PBI-02-04) is mapped to Ollama's documented OpenAI-compatible `tools=`/`message.tool_calls` shape, adapted for two real differences (a synthesized `call_id`, since Ollama assigns none, and already-parsed-dict arguments instead of a JSON string) — and this mapping was genuinely live-verified, not just unit-tested, because a real local Ollama server with a tool-calling-capable model (`llama3.2:3b`) turned out to be running in this development environment (see `validation.md`/`decisions.md` for the real `POST /chat` round trip, including a real Tool execution and an important architectural observation about LLM-fabricated Tool arguments staying safely isolated from the business-fact response text). `docker-compose.yml`'s `api` service gained `extra_hosts: host.docker.internal:host-gateway` so a containerized API can reach a host-run Ollama server (Ollama itself is intentionally not containerized); `apps/api/Dockerfile` now installs `aiohttp` unconditionally so the Ollama path works inside the built image without a rebuild. `InMemoryConversationRepository` and `LocalKnowledgeProvider` were confirmed as the unchanged local defaults (zero Cosmos/Azure AI Search dependency for local execution). `.env.example` documents every environment variable a fully local run requires (`LLM_PROVIDER`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT_SECONDS`). 398 tests pass deterministically (17 new: `tests/unit/llm/test_ollama_provider.py` (13) plus one new factory-selection test and 3 pre-existing regression assertions unaffected); ruff and mypy clean after one well-understood, justified fix (`Self` return type annotation on async context manager test doubles). `docker compose config` validated structurally (Docker daemon itself was unavailable in this environment — documented as an environmental limitation, not a code defect). No Azure deployment, Cosmos production wiring, Azure networking, APIM, authentication, new agents, or new RAG features implemented. — 2026-08-07
Evidence: `docs/sprint_03/evidence/pbi-03-01-ollama-provider-validation.txt`

## Sprint validation

See `validation.md`.

## Sprint retrospective

Complete when closing the sprint:

- What worked:
- What did not:
- Technical debt:
- Security findings:
- Follow-up PBIs:

# Sprint 01 — Core Multi-Agent Platform

## Objective

Build the core multi-agent orchestration platform: the Conversation API, context management,
the Supervisor orchestration framework, intent classification, registry-driven agent routing,
guardrails, and a human-escalation foundation — per `CLAUDE.md` §14's Sprint 01 scope.

## Scope

- Supervisor orchestration framework (interfaces, registry-driven routing, no concrete-agent
  coupling).
- Rule-based intent resolution (no LLM yet).
- Mock domain agents validating the registry pattern (Claims, Broker, Commercial Intake).
- `POST /chat` conversational entry point.
- Conversation persistence through the existing `ConversationRepository` (PBI-00-05).
- Further Sprint 01 PBIs (real agent business logic, LLM-backed intent classification,
  guardrails, human escalation, Tool registry/contracts) will be defined and added to the
  Deliverables list below as they are scoped — only PBI-01-01 is defined at Sprint start.

## Out of scope

- Azure OpenAI / Semantic Kernel / AutoGen / LangGraph / CrewAI.
- Prompt engineering, RAG, Azure AI Search, vector databases.
- Real Tool Calling against business systems.
- Authentication (Entra ID end-user login).
- Real insurance business logic in any agent.

## Deliverables

- [x] PBI-01-01: Build the Supervisor Agent orchestration framework.
- [x] PBI-01-02: Build the reusable Agent Tool Framework.
- [x] PBI-01-03: Build the reusable Prompt Management Framework.
- [x] PBI-01-04: Build the reusable LLM Adapter Framework with Mock and Azure OpenAI providers.

## Acceptance criteria

| ID | Criterion | Evidence expected |
|---|---|---|
| AC-01 | Supervisor depends only on interfaces (Agent/IntentResolver/AgentRegistry Protocols), never on concrete agents | Code review — no concrete agent import in `src/supervisor/` |
| AC-02 | Agent routing is registry-driven, no if/else on intent | Code review — `orchestrator.py` |
| AC-03 | `POST /chat` exercises the full pipeline (Supervisor → Intent → Registry → Agent → Repository → JSON) | Unit + integration-style API test, evidence log |
| AC-04 | 100% deterministic tests, no Azure dependency | `pytest` evidence |
| AC-05 | `ruff`/`mypy` clean | Evidence log |
| AC-06 | API Docker image remains buildable after the shared-package wiring | `docker build`/`docker compose config` evidence |
| AC-07 | Agents depend only on Tool abstractions (`ToolExecutor`), never a concrete Tool or integration | Code review — `src/agents/claims_agent.py`, `src/tools/` |
| AC-08 | Tool routing is registry-driven; duplicate registration and missing-tool resolution both fail with typed errors | Code review + `pytest` evidence — `src/tools/registry.py` |
| AC-09 | `ToolExecutor` never raises to its caller — always returns a typed `ToolResult` | `pytest` evidence — `tests/unit/tools/test_executor.py` |
| AC-10 | Agents depend only on `PromptManager`; no prompt text embedded in Agent code | Code review — `src/agents/claims_agent.py` + `tests/unit/agents/test_claims_agent_prompt_integration.py` |
| AC-11 | Prompt rendering is deterministic and safe: no `eval()`, missing required variables and unexpected variables both fail explicitly | `pytest` evidence — `tests/unit/prompts/test_renderer.py` |
| AC-12 | Prompt identifiers are logical (`claims.system`), never storage paths, and map to CLAUDE.md's existing `configs/prompts/` folders | Code review — `src/prompts/filesystem_provider.py` |
| AC-13 | Agents depend only on `LLMProvider`; no Azure SDK/OpenAI SDK import in any Agent | Code review — `src/agents/claims_agent.py` |
| AC-14 | `MockLLMProvider` is deterministic and is the default provider; tests require no Azure connectivity | `pytest` evidence — `tests/unit/llm/test_mock_provider.py` |
| AC-15 | `AzureOpenAIProvider` is production-shaped (typed config, no hardcoded endpoint/deployment/key, Entra ID preferred, API key via `SecretProvider` only) but never called during tests | Code review + `pytest` evidence — `tests/unit/llm/test_azure_openai_provider.py` (fully mocked) |

## Dependencies

- Everything already established in Sprint 00: `apps/api`, `src/domain`, `src/services`,
  `src/config`, root `pyproject.toml`, CI pipeline.

## Risks

| Risk | Probability | Impact | Mitigation |
|---|---:|---:|---|
| Sprint 00 formally still has 2 open PBIs (00-08, 00-09) when Sprint 01 starts | N/A (accepted) | Media | User explicitly accepted this risk for PBI-01-01; see `docs/sprint_00/decisions.md`. Sprint 00 closure is unaffected by Sprint 01 progress and remains trackable independently. |
| Cross-package dependency (`apps/api` → root `src/`) breaks the Docker image | Media | Alta | Addressed directly in PBI-01-01 as a prerequisite fix (build context + `PYTHONPATH`), validated via `docker compose config` / `docker build` |

## Deliverable Log

<!-- Append entries. Do not remove previous entries. -->

PBI-01-01: Supervisor orchestration framework built (`src/supervisor/`): `Supervisor`/`Agent`/`IntentResolver`/`AgentRegistry` Protocols, `SupervisorOrchestrator` (depends only on interfaces, never a concrete agent, registry-driven routing with no if/else/switch), `RuleBasedIntentResolver` (deterministic keyword matching, no AI), `InMemoryAgentRegistry`, and 4 deterministic mock agents (`ClaimsAgent`, `BrokerAgent`, `CommercialIntakeAgent`, and `FallbackAgent` for `UNKNOWN` — the 4th is a deliberate addition beyond the 3 explicitly requested, keeping the registry total). `POST /chat` exposed via `apps/api/src/api/routes/chat.py`, composed in `apps/api/src/api/dependencies.py`. Fixed a real Docker build-context gap (API image had no access to the shared `src/` package) as a prerequisite, not scope creep. 60/60 new+existing unit tests pass deterministically with no Azure dependency (2 unrelated live-integration scaffolds skip as designed); ruff and mypy clean; live smoke test confirmed the full `POST /chat → Supervisor → Intent → Registry → Agent → Repository → JSON` pipeline against a running server. No Azure OpenAI, RAG, APIM, or business logic implemented. Started with Sprint 00 not yet formally closed (PBI-00-08/09 open) — user explicitly accepted this risk; see `docs/sprint_00/decisions.md`. — 2026-08-07
Evidence: `docs/sprint_01/evidence/pbi-01-01-supervisor-orchestration-validation.txt`

PBI-01-02: Reusable Agent Tool Framework built (`src/tools/`), mirroring the Supervisor framework's shape: `Tool` (generic `Protocol[ToolInputT]`), `ToolRegistry` Protocol + `InMemoryToolRegistry` (duplicate `register()` raises `ToolAlreadyRegisteredError`, unlike `AgentRegistry`'s silent overwrite), `ToolExecutor` (resolves → validates typed input → executes → normalizes every failure into a typed `ToolResult`, never raises to its caller, no business logic). Fully typed contracts (`ToolRequest`, `ToolResult[T]`, `ToolMetadata`, `ToolExecutionContext`) with exactly one deliberately-justified untyped boundary (`ToolRequest.tool_input: dict[str, Any]`, before schema resolution). Three synthetic Tools (`PolicyLookupTool`, `ClaimsStatusTool`, `BrokerAccountLookupTool`) under `src/services/tools/`, backed by a small (2 records each) isolated synthetic-data provider package — no real TMX data, no external calls. `ClaimsAgent` modified to depend on `ToolExecutor` (never a concrete Tool) via constructor injection, composed in the extended `apps/api/src/api/dependencies.py`; the Supervisor remains completely unaware of Tools. 82/82 tests pass deterministically with no Azure dependency (full Supervisor + `/chat` regression suite unchanged and passing); ruff and mypy clean; live smoke test confirmed the tool result flowing through a real `POST /chat` call. Branch topology note: this PBI's branch was cut before PBI-01-01 was merged to `main`; resolved via a clean fast-forward merge before work began (see decisions.md). No Azure OpenAI, RAG, APIM, real integrations, or real business data implemented. — 2026-08-07
Evidence: `docs/sprint_01/evidence/pbi-01-02-tool-framework-validation.txt`

PBI-01-03: Reusable Prompt Management Framework built (`src/prompts/`), mirroring the Supervisor and Tool frameworks' interface-only shape a third time: `PromptProvider` Protocol, `PromptManager` (loads, renders, returns metadata, normalizes unexpected provider failures into typed `PromptValidationError` — no LLM calls), `FileSystemPromptProvider` (the only component aware of Markdown/YAML/file paths). Fully typed contracts (`PromptDefinition`, `RenderedPrompt`, `PromptMetadata`, `PromptRenderContext`, `PromptVersion`). Prompts live as Markdown-with-YAML-frontmatter files in CLAUDE.md's already-reserved `configs/prompts/{supervisor,claims,broker_services,commercial_intake}/` folders (from PBI-00-01) plus a new `fallback/` folder, carrying exactly the metadata CLAUDE.md §9 requires (version, purpose, allowed tools, prohibited decisions, change notes). Logical identifiers (`claims.system`, `broker.system`, ...) map to those folders via an explicit table — proving the abstraction is real (`broker` → `broker_services`, not a trivial rename). Rendering is a safe, deterministic regex substitution over exactly 6 known variables (`conversationId`/`userId`/`intent`/`conversationSummary`/`toolSummaries`/`agentName`) — no `eval()`, no templating engine; missing required variables and unexpected/unknown variables both fail explicitly with `PromptRenderError`. `ClaimsAgent` extended with `PromptManager` injection (alongside its existing `ToolExecutor` injection from PBI-01-02) with zero embedded prompt text — a dedicated test asserts the prompt's actual wording never appears in the agent's source file. Fixed a real Docker packaging gap as a prerequisite (`configs/prompts/` was never copied into the API image; `pyyaml` added to the image's pip install and to `pyproject.toml`'s core dependencies, not an optional extra). 108/108 tests pass deterministically with no Azure dependency, clean on the first run (full Supervisor + Tool + `/chat` regression suite unchanged and passing); ruff and mypy clean on the first run; live smoke test confirmed a rendered prompt's identifier/version flowing through a real `POST /chat` call. No Azure OpenAI, LLM calls, RAG, Semantic Kernel, LangGraph, CrewAI, AutoGen, APIM, or real business prompts implemented. — 2026-08-07
Evidence: `docs/sprint_01/evidence/pbi-01-03-prompt-framework-validation.txt`

PBI-01-04: Reusable LLM Adapter Framework built (`src/llm/`), mirroring the Supervisor/Tool/Prompt frameworks' interface-only shape a fourth time: `LLMProvider` Protocol (`async generate(LLMRequest) -> LLMResponse`), `MockLLMProvider` (fully deterministic, default, zero Azure dependency), `AzureOpenAIProvider` (production-shaped, lazily imported so the `openai`/`azure-identity` SDKs are never required unless `LLM_PROVIDER=azure_openai`). Fully typed contracts (`LLMMessage`, `LLMRequest`, `LLMResponse`, `LLMUsage`, `LLMGenerationSettings` with real Pydantic field bounds on temperature/max tokens/timeout) and a typed exception hierarchy (`LLMConfigurationError`, `LLMProviderError` → `LLMRateLimitError`/`LLMTimeoutError`/`LLMContentSafetyError`) mapped from the real `openai` SDK's own exceptions. `AzureOpenAIProvider` prefers Microsoft Entra ID (`DefaultAzureCredential` + `get_bearer_token_provider`); API-key auth, if explicitly enabled, is read only through the existing `SecretProvider` abstraction using the `azure-openai-api-key` secret name already reserved in PBI-00-06 — never `os.environ` inside the provider. `ClaimsAgent` extended with `LLMProvider` injection (alongside its existing `ToolExecutor` and `PromptManager` injections): its response text now genuinely comes from the LLM call, which surfaced one expected, correctly-fixed test update (an old "response identical regardless of input" assertion no longer holds now that the response legitimately depends on input — replaced with an assertion on what's still actually invariant). 136/136 tests pass deterministically with no Azure dependency (full Supervisor + Tool + Prompt + `/chat` regression suite confirmed passing); ruff and mypy clean after fixing two real, well-understood friction points (a `TYPE_CHECKING`-only forward reference, and an explicit justified `cast()` for the `openai` SDK's `TypedDict` message params); live smoke test confirmed a deterministic mock LLM response flowing through a real `POST /chat` call. No Docker changes were needed (mock provider needs no extra packages in the image). No RAG, Azure AI Search, embeddings, vector databases, Semantic Kernel, AutoGen, LangGraph, CrewAI, APIM, or authentication implemented. — 2026-08-07
Evidence: `docs/sprint_01/evidence/pbi-01-04-llm-adapter-validation.txt`

## Sprint validation

See `validation.md`.

## Sprint retrospective

Complete when closing the sprint:

- What worked:
- What did not:
- Technical debt:
- Security findings:
- Follow-up PBIs:

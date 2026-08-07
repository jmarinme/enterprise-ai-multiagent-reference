# Sprint 01 Validation

Record only commands actually executed and their real results.

## 2026-08-07 — PBI-01-01: Supervisor Agent orchestration framework

| Command | Result |
|---|---|
| `pytest tests/unit/api tests/unit/domain tests/unit/services tests/unit/supervisor tests/unit/agents tests/integration -v` | `60 passed, 2 skipped` |
| `ruff check apps/api/src src tests` | Attempt 1: 4 errors (3× import ordering, 1× unused variable). Fixed. Attempt 2: `All checks passed!` |
| `mypy apps/api/src` / `mypy src` | Both clean (13 and 29 files) |
| `mypy tests/unit/supervisor tests/unit/agents` | Clean (5 files). `tests/unit/api/*` excluded — pre-existing, unrelated static-analysis limitation (mypy can't see `conftest.py`'s runtime `sys.path` insertion); affects every file in that directory since PBI-00-02, not just the new one |
| Live smoke test: `uvicorn` + two real `POST /chat` calls | Both returned `200` with the full expected shape; one routed to `ClaimsAgent`, one to `FallbackAgent` |
| `docker compose config` (temporary local `.env`) | exit 0 — confirms the API build context/dockerfile fix resolved correctly |
| `docker build` | NOT executed — Docker daemon unavailable locally (recurring environmental limitation) |
| Manual grep for secrets/keys and prohibited frameworks (OpenAI/Semantic Kernel/AutoGen/LangGraph/CrewAI) | Clean — all matches are comments stating what is *not* used |

Full output archived at `docs/sprint_01/evidence/pbi-01-01-supervisor-orchestration-validation.txt`.

Conclusion: the Supervisor orchestration framework is implemented, fully interface-driven (no concrete-agent coupling, no if/else routing), and validated end-to-end via both automated tests and a live HTTP smoke test. The prerequisite Docker build-context fix keeps the API image's shape correct; the actual image build remains unverified locally pending a running Docker daemon. No Azure OpenAI, RAG, APIM, or business logic was implemented.

## 2026-08-07 — PBI-01-02: Reusable Agent Tool Framework

| Command | Result |
|---|---|
| `git merge-base HEAD feat/pbi-01-01-supervisor-agent` + `git merge ... --ff-only` | Confirmed a pure fast-forward candidate (zero divergence); merge succeeded cleanly, 32 files, no conflicts — brought PBI-01-01's work onto this branch before any PBI-01-02 work began |
| `pytest tests/unit/api tests/unit/domain tests/unit/services tests/unit/supervisor tests/unit/agents tests/unit/tools tests/integration -v` | Attempt 1: collection error (`test_registry.py` basename collision between `tests/unit/tools/` and `tests/unit/supervisor/`, same recurring class of issue as PBI-00-02/00-06). Fixed by renaming to `test_tool_registry.py`. Attempt 2: `82 passed, 2 skipped` |
| `ruff check apps/api/src src tests` | Attempt 1: 1 error (`UP046`, ruff recommending Python 3.12-only PEP 695 generic syntax that would be a `SyntaxError` under the 3.11.9 interpreter used for local validation). Suppressed with a justified, targeted `# noqa: UP046`. Attempt 2: `All checks passed!` |
| `mypy apps/api/src` / `mypy src` | Both clean (13 and 41 files) |
| `mypy tests/unit/tools tests/unit/agents tests/unit/supervisor` | Clean (9 files). `tests/unit/api/*` excluded for the same pre-existing, unrelated reason as PBI-01-01 |
| Live smoke test: `uvicorn` + real `POST /chat` call routed to `ClaimsAgent` | `200`, response includes the live synthetic tool result (`status=under_review`), proving the full `Agent → ToolExecutor → ToolRegistry → Tool → ToolResult → Agent` chain end-to-end through the real composed API |
| Manual grep for secrets/keys, prohibited frameworks, and real TMX data references | Clean — all matches are comments/docstrings explicitly stating what is *not* used |

Full output archived at `docs/sprint_01/evidence/pbi-01-02-tool-framework-validation.txt`.

Conclusion: the Tool framework mirrors the Supervisor framework's proven interface-only shape; `ToolExecutor` never contains business logic and never raises to its caller; `ToolRegistry` fails explicitly on duplicate registration and on missing tools; every public contract is typed except one deliberately-justified boundary. `ClaimsAgent` now demonstrates real `ToolExecutor` injection with the Supervisor remaining completely unaware of Tools. All 82 tests pass deterministically with no Azure dependency (full regression of the existing Supervisor and `/chat` suites confirmed unchanged); ruff and mypy clean. No Azure OpenAI, RAG, APIM, real integrations, or real business data was implemented.

## 2026-08-07 — PBI-01-03: Reusable Prompt Management Framework

| Command | Result |
|---|---|
| Branch topology check (`git log`) | Confirmed both PBI-01-01 and PBI-01-02 already merged into this branch's history — no merge needed this time |
| `pytest tests/unit/api tests/unit/domain tests/unit/services tests/unit/supervisor tests/unit/agents tests/unit/tools tests/unit/prompts tests/integration -v` | `108 passed, 2 skipped` — clean on the first run |
| `ruff check apps/api/src src tests` | `All checks passed!` — clean on the first run |
| `mypy apps/api/src` / `mypy src` | Both clean (13 and 48 files) |
| `mypy tests/unit/prompts tests/unit/agents tests/unit/tools tests/unit/supervisor` | Clean (13 files). `tests/unit/api/*` excluded for the same pre-existing, unrelated reason as PBI-01-01/02 |
| Live smoke test: `uvicorn` + real `POST /chat` call routed to `ClaimsAgent` | `200`, response includes `[prompt=claims.system@1.0.0]`, proving the full `Agent → PromptManager → PromptProvider → PromptDefinition → renderer → RenderedPrompt` chain end-to-end through the real composed API |
| `docker compose config` (temporary local `.env`) | exit 0 — `api.build.context`/`dockerfile` unaffected and still correct after the Dockerfile edit |
| `docker build` | NOT executed — Docker daemon unavailable locally (same recurring environmental limitation) |
| Manual grep for secrets/keys, prohibited frameworks, and real TMX/business content in prompt files | Clean — all matches are comments/docstrings explicitly stating what is *not* used; all 5 prompt files are generic synthetic placeholder wording |

Full output archived at `docs/sprint_01/evidence/pbi-01-03-prompt-framework-validation.txt`.

Conclusion: the Prompt Management framework mirrors the Supervisor and Tool frameworks' proven interface-only shape; `PromptManager` makes no LLM calls, contains no business logic, and normalizes unexpected provider failures into a typed `PromptValidationError`. `FileSystemPromptProvider` is the only component aware of file paths/YAML/Markdown. Rendering is safe and deterministic (no `eval()`), failing explicitly for both missing required and unexpected/unknown variables. `ClaimsAgent` now demonstrates real `PromptManager` injection with zero embedded prompt text, verified by a dedicated test. All 108 tests pass deterministically with no Azure dependency (full regression of the existing Supervisor, Tool, and `/chat` suites confirmed unchanged); ruff and mypy clean. No Azure OpenAI, LLM calls, RAG, Semantic Kernel, LangGraph, CrewAI, AutoGen, APIM, or real business prompts were implemented.

## 2026-08-07 — PBI-01-04: Reusable LLM Adapter Framework

| Command | Result |
|---|---|
| Branch topology check (`git log`) | Confirmed PBI-01-01/02/03 already merged into this branch's history — no merge needed |
| `pytest tests/unit/api tests/unit/domain tests/unit/services tests/unit/supervisor tests/unit/agents tests/unit/tools tests/unit/prompts tests/unit/llm tests/integration -v` | Attempt 1: `135 passed, 1 failed, 2 skipped` — one *expected* behavior-change failure (see decisions.md), not a regression bug. Fixed the outdated test assertion. Attempt 2: `136 passed, 2 skipped` |
| `ruff check apps/api/src src tests` | Attempt 1: 2 errors (a `TYPE_CHECKING`-resolvable forward-reference name, plus one import-ordering issue). Fixed. Attempt 2: `All checks passed!` |
| `mypy apps/api/src` / `mypy src` | Attempt 1: 2 errors in `azure_openai_provider.py` (ambiguous `TypedDict` match for the `openai` SDK's chat message params). Fixed with an explicit, justified `cast()`. Attempt 2: both clean (13 and 55 files) |
| `mypy tests/unit/llm tests/unit/agents tests/unit/tools tests/unit/prompts tests/unit/supervisor` | Attempt 1: 1 error (unused `type: ignore`). Fixed. Attempt 2: clean (18 files) |
| Live smoke test: `uvicorn` + real `POST /chat` call routed to `ClaimsAgent` | `200`, response includes the deterministic mock LLM text plus `[prompt=claims.system@1.0.0]` and the tool-lookup summary, proving the full `Agent → PromptManager → RenderedPrompt → LLMProvider → MockLLMProvider → LLMResponse` chain end-to-end through the real composed API |
| `docker compose config` (temporary local `.env`) | exit 0 — unaffected, no Dockerfile changes this PBI |
| `docker build` | NOT executed — Docker daemon unavailable locally; not required this PBI (no image content changed) |
| Manual grep for secrets/keys, hardcoded endpoints, and prohibited frameworks/services (RAG/Azure AI Search/APIM/Semantic Kernel/AutoGen/LangGraph/CrewAI/embeddings/vector DBs) | Clean — only obviously-fake test fixture values (`example.openai.azure.com`, `mock-secret-value-not-a-real-key`) |

Full output archived at `docs/sprint_01/evidence/pbi-01-04-llm-adapter-validation.txt`.

Conclusion: the LLM Adapter framework mirrors the Supervisor/Tool/Prompt frameworks' proven interface-only shape a fourth time; `MockLLMProvider` is fully deterministic and is the default, so all 136 tests run with zero Azure connectivity. `AzureOpenAIProvider` is production-shaped and fully mocked in its own 9 dedicated tests — never called against real Azure. `ClaimsAgent` now demonstrates real `LLMProvider` injection, and one outdated pre-PBI-01-04 test assertion was correctly updated to reflect the agent's new (intended) input-dependent behavior. ruff and mypy clean after two well-understood, justified fixes. No RAG, Azure AI Search, embeddings, vector databases, Semantic Kernel, AutoGen, LangGraph, CrewAI, APIM, or authentication was implemented.

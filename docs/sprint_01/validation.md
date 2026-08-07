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

## 2026-08-07 — PBI-01-05: First functional Claims Agent (claim-notice intake flow)

| Command | Result |
|---|---|
| Branch topology check (`git log`, `git branch -a`) | Confirmed `feat/pbi-01-05-claims-agent` was cut from the already-merged PBI-01-04 tip (`e38ea74`), same commit as `main` — no merge needed |
| `pytest tests/unit/api tests/unit/domain tests/unit/services tests/unit/supervisor tests/unit/agents tests/unit/tools tests/unit/prompts tests/unit/llm tests/integration -v` | Attempt 1: `177 passed, 2 failed, 2 skipped` — 2 failures, both understood before fixing (see below). Attempt 2 (after fixes): `182 passed, 2 skipped` |
| Failure 1 (own test bug) | `test_conversation_continues_gracefully_after_an_unknown_policy_number` assumed policy validation happens immediately after the policy number is supplied; the actual (correct, intentional) design only validates once every required field is collected. Fixed the test to complete the full intake with the unrecognized number before asserting the "not found" notice |
| Failure 2 (real product bug, found by the new `POST /chat` E2E test) | `SupervisorOrchestrator` re-resolves intent from every individual message via keyword matching (`RuleBasedIntentResolver`), so a bare follow-up like a policy number or a plain "yes"/"no" has no CLAIMS keywords and was misrouted to `FallbackAgent` mid claims-intake, breaking the multi-turn flow through the real API. Fixed with one uniform, agent-agnostic fallback rule in `SupervisorOrchestrator._resolve_agent()`: an `UNKNOWN`-classified follow-up stays with the conversation's current agent (via a new `ConversationContext.current_agent` field, populated from `Conversation.current_agent`) rather than falling through to `FallbackAgent` — not per-agent-type branching, applies identically regardless of which Agent is current. See decisions.md |
| `ruff check apps/api/src src tests` | Attempt 1: 1 error (`BLE001`, blind `except Exception` in `ClaimsAgent.handle()`'s outermost safety boundary). Suppressed with a justified, targeted `# noqa: BLE001` (same pattern as PBI-01-02's `# noqa: UP046`). Attempt 2: `All checks passed!` |
| `mypy apps/api/src` / `mypy src` | Both clean (13 and 62 files) |
| `mypy tests/unit/llm tests/unit/agents tests/unit/tools tests/unit/prompts tests/unit/supervisor tests/unit/services` | Clean (29 files). `tests/unit/api/*` excluded for the same pre-existing, unrelated reason as every prior PBI this sprint |
| Live smoke test: `uvicorn` + a full 10-turn `POST /chat` claim report | All 10 turns returned `200`; the flow correctly asked one question at a time for each missing field, validated the policy (`SYN-POL-0001`, active + payment current), registered a synthetic claim (`SYN-CLM-2026-0001`), and assigned a synthetic adjuster (`Synthetic Adjuster Chen`) — full transcript archived. A separate call for an unrelated message ("hello, good morning") confirmed `FallbackAgent` routing is unaffected for genuinely new conversations |
| `docker compose config` (temporary local `.env` copied from `.env.example`, removed after) | exit 0 — unaffected, no Dockerfile/compose changes this PBI |
| `docker build` | NOT executed — Docker daemon unavailable locally (recurring environmental limitation) |
| Manual grep for secrets/keys, prohibited frameworks (Semantic Kernel/AutoGen/LangGraph/CrewAI), and real TMX/business data across every new/changed claims file | Clean — no matches |

Full output (pytest, ruff, mypy, and the real smoke-test transcript) archived at `docs/sprint_01/evidence/pbi-01-05-claims-agent-validation.txt`.

Conclusion: `ClaimsAgent` is now a real, functional, deterministic (with `MockLLMProvider`) multi-turn claims-intake agent — the first agent in this platform to contain actual business orchestration rather than proving a framework's wiring. Every business fact is deterministic and Tool-sourced; the LLM is never the source of a business fact, satisfying CLAUDE.md §3 while still keeping `PromptManager`/`LLMProvider` genuinely wired every turn. Only "policy not found" blocks progression, keeping the Agent strictly within its permitted scope (no coverage determination, no claim rejection, no indemnity authorization). One real, blocking Supervisor routing bug was found and fixed via the new end-to-end `POST /chat` test — proof that the broader (not just unit-level) test coverage this PBI required was worth writing. All 182 tests pass deterministically with no Azure dependency; ruff and mypy clean after one well-understood, justified fix. No real claims system, real customer data, RAG, Azure AI Search, APIM, authentication, document upload/OCR, coverage adjudication, fraud detection, payments, claims settlement, or additional agent framework was implemented.

## 2026-08-07 — PBI-01-06: Functional Broker Agent (broker-services support flow)

| Command | Result |
|---|---|
| Branch topology check (`git log`, `git rev-parse main HEAD`) | Confirmed `feat/pbi-01-06-broker-agent` was cut from the already-merged PBI-01-05 tip (`72b27e8`), same commit as `main` — no merge needed |
| `pytest tests/unit/api tests/unit/domain tests/unit/services tests/unit/supervisor tests/unit/agents tests/unit/tools tests/unit/prompts tests/unit/llm tests/integration -v` | Attempt 1: collection error (`test_state.py`/`test_extraction.py`/`test_workflow.py` basename collisions between `tests/unit/agents/broker/` and `tests/unit/agents/claims/`, same recurring class of issue as PBI-01-02/00-02/00-06). Fixed by renaming to `test_broker_state.py`/`test_broker_extraction.py`/`test_broker_workflow.py`. Attempt 2: `234 passed, 2 skipped` — clean, zero test failures |
| `ruff check apps/api/src src tests` | Attempt 1: 1 error (unused import after a rename). Fixed. Attempt 2: `All checks passed!` |
| `mypy apps/api/src` / `mypy src` | Both clean (13 and 69 files) |
| `mypy tests/unit/llm tests/unit/agents tests/unit/tools tests/unit/prompts tests/unit/supervisor tests/unit/services` | Attempt 1: 1 error (unused `type: ignore` — `LLMProvider` is a Protocol, so a structurally-matching stub needs no suppression, unlike the concrete `PromptManager` class in the same test). Fixed. Attempt 2: clean (36 files) |
| Live smoke test #1: `uvicorn` + `POST /chat` with PBI-01-06's own literal example ("I want to know the status of a policy.") | Routed to `FallbackAgent`, not `BrokerAgent` — a real bug in `RuleBasedIntentResolver`, not a `BrokerAgent` defect (`_BROKER_KEYWORDS` required the exact substring `"policy status"`, which this phrasing does not contain). Fixed by adding bare `"policy"`/`"transaction"` keywords; added regression cases to `tests/unit/supervisor/test_intent.py` and a dedicated `tests/unit/api/test_chat.py` E2E test using the literal phrase |
| Live smoke test #2 (after the intent-resolver fix): full policy-status conversation | `200` on both turns, correctly routed to `BrokerAgent`, reported "Policy SYN-POL-0001 status: active. Payments on this policy are up to date." — but the fact was stated **twice** in one response (same-turn fall-through from the lookup handler into `_handle_completed`'s summary). A real `BrokerAgent` workflow bug, not a test artifact. Fixed by ending the turn right after the lookup notice (`should_continue=False`) instead of continuing into a same-turn completion summary; added a regression assertion (`combined.count(...) == 1`) to `tests/unit/agents/broker/test_broker_workflow.py` |
| `pytest` re-run after both fixes | `237 passed, 2 skipped` (3 new regression tests added: 2 intent-resolver cases + 1 E2E test) |
| `ruff check` / `mypy` re-run after both fixes | Both clean |
| Live smoke test #3 (final, clean): `uvicorn` + real `POST /chat` covering policy status, commission-with-successful-payment-request (+ duplicate-request re-message), transaction status, and fallback-for-unrelated-conversation | All turns `200`, all facts reported exactly once, duplicate payment request correctly blocked with the existing reference, fallback routing unaffected — full transcript archived |
| `docker compose config` (temporary local `.env` copied from `.env.example`, removed after) | exit 0 — unaffected, no Dockerfile/compose changes this PBI |
| `docker build` | NOT executed — Docker daemon unavailable locally (recurring environmental limitation) |
| Manual grep for secrets/keys, prohibited frameworks (Semantic Kernel/AutoGen/LangGraph/CrewAI), and real TMX/business data across every new/changed broker file | Clean — no matches |

Full output (pytest, ruff, mypy, and the real smoke-test transcript) archived at `docs/sprint_01/evidence/pbi-01-06-broker-agent-validation.txt`.

Conclusion: `BrokerAgent` is now a real, functional, deterministic (with `MockLLMProvider`) multi-turn broker-services agent, structurally mirroring `ClaimsAgent` without sharing code with it (a deliberate, documented "not yet" on extraction — see decisions.md). Reuses `PolicyLookupTool`/`PaymentStatusTool`/`BrokerAccountLookupTool` unmodified rather than duplicating the PBI's own suggested (but redundant) `PolicyStatusTool`/`PolicyPaymentStatusTool`; reuses the PBI-01-05 metadata round-trip and Supervisor routing-continuity fallback with zero modification, proving both are genuinely agent-agnostic. Two real bugs were found and fixed via live end-to-end validation (an intent-resolver gap that blocked the PBI's own example phrasing, and a same-turn duplicated-notice workflow bug) — both are exactly the kind of defect unit tests calling the Agent directly cannot catch, reinforcing why this PBI's required `POST /chat` E2E and live-smoke-test coverage matters. All 237 tests pass deterministically with no Azure dependency; ruff and mypy clean after well-understood, justified fixes. No real broker/policy/commission system, real customer data, real financial transaction/payment execution, RAG, Azure AI Search, APIM, or authentication was implemented.

# Sprint 02 — Knowledge / RAG Foundation

## Objective

Build the reusable knowledge-retrieval (RAG) abstraction future RAG-enabled agents will use,
per CLAUDE.md §4.4 ("RAG is documentary only... must provide source references and must not
replace Tools for live business data"), and integrate it into at least one existing agent
without rewriting that agent's business workflow.

## Scope

- Typed Knowledge/RAG framework (`src/rag/`): `KnowledgeProvider` Protocol, `KnowledgeRetriever`,
  `KnowledgeQuery`, `KnowledgeChunk`, `KnowledgeResult`, `KnowledgeMetadata`, typed exceptions.
- Deterministic `LocalKnowledgeProvider` (keyword/text scoring) over a small set of synthetic
  Markdown knowledge documents (`configs/knowledge_base/`) — no embeddings, no vector database.
- Integration into `ClaimsAgent` via dependency injection: retrieved knowledge feeds the
  existing `PromptManager`/`LLMProvider` flow as documentary context only, never a business
  fact, and never touches `ClaimsIntakeState`.
- `AzureAISearchProvider`: a second, production-shaped `KnowledgeProvider` implementation
  (PBI-02-02), configuration-selected, local remains the default for dev/tests. Reusable Bicep
  module provisioning the Azure AI Search *service* only (no index, no ingestion, no
  deployment performed).

## Out of scope

- Embeddings, vector databases, semantic ranking (not justified for this synthetic corpus).
- Real company/customer documents.
- RAG evaluation/quality metrics.
- RAG index creation and document ingestion pipelines.
- APIM, authentication, Azure deployment.
- Integrating Knowledge retrieval into Broker or Commercial Intake (deferred — only one agent
  was required this PBI; see `decisions.md`).

## Deliverables

- [x] PBI-02-01: Build the reusable Knowledge / RAG Framework.
- [x] PBI-02-02: Implement the Azure AI Search KnowledgeProvider.

## Acceptance criteria

| ID | Criterion | Evidence expected |
|---|---|---|
| AC-01 | Agents depend only on `KnowledgeRetriever`/typed `src.rag` models, never on Azure AI Search or any concrete provider | Code review — `src/agents/claims_agent.py`, `src/rag/provider.py` |
| AC-02 | `LocalKnowledgeProvider` retrieval is fully deterministic (no embeddings, no randomness) and isolated behind the `KnowledgeProvider` Protocol | Code review — `src/rag/local_provider.py`; `pytest` evidence — `tests/unit/rag/test_local_provider.py::test_retrieval_is_deterministic_across_repeated_calls` |
| AC-03 | Retrieval results carry source/document identifiers and metadata sufficient for a future citation | `pytest` evidence — `tests/unit/rag/test_local_provider.py::test_chunks_carry_source_and_metadata_for_future_citations` |
| AC-04 | Top-k is supported and enforced via a typed, bounded field; "no results" is an explicit, non-exceptional empty-chunks result | `pytest` evidence — `tests/unit/rag/test_local_provider.py::test_top_k_caps_the_number_of_returned_chunks`, `::test_no_results_for_a_query_with_no_keyword_overlap`; `tests/unit/rag/test_rag_models.py` |
| AC-05 | An invalid `KnowledgeQuery` (empty text, non-positive/out-of-bound top_k) is rejected at construction, never reaching a provider | `pytest` evidence — `tests/unit/rag/test_rag_models.py::test_knowledge_query_rejects_empty_text`, `::test_knowledge_query_rejects_non_positive_top_k`, `::test_knowledge_query_rejects_top_k_above_the_bound` |
| AC-06 | `ClaimsAgent` retrieves knowledge and threads it into its existing `PromptManager`/`LLMProvider` flow without rewriting `src/agents/claims/workflow.py` or `state.py` | Code review — `src/agents/claims_agent.py` diff is additive only to those files (zero changes) |
| AC-07 | Retrieved knowledge never becomes a business fact and never blocks or alters the deterministic business-fact text, with or without a match | `pytest` evidence — `tests/unit/agents/test_claims_agent_knowledge_integration.py::test_retrieved_knowledge_never_changes_the_deterministic_business_fact_text` |
| AC-08 | Knowledge retrieval failure degrades gracefully — same pattern as Prompt/LLM failure, never a raw exception or blocked response | `pytest` evidence — `tests/unit/agents/test_claims_agent_knowledge_integration.py::test_agent_degrades_gracefully_when_the_knowledge_retriever_fails` |
| AC-09 | Supervisor remains completely unaware of the Knowledge implementation | Code review — no `src/rag` import anywhere under `src/supervisor/` |
| AC-10 | Claims/Broker/Commercial conversational flows and `POST /chat`'s contract remain backward-compatible | `pytest` evidence — full pre-existing regression suite passes unchanged |
| AC-11 | A full `POST /chat` call for a relevant Claims message produces a provable `[knowledge=...]` annotation through the real composition root | `pytest` evidence — `tests/unit/api/test_chat.py::test_chat_claims_response_includes_a_knowledge_annotation_through_the_real_api`; live smoke test |
| AC-12 | `AzureAISearchProvider` implements the same `KnowledgeProvider` Protocol as `LocalKnowledgeProvider`, with zero Agent code changes required to select it | Code review — `src/rag/azure_ai_search_provider.py` structurally implements `src/rag/provider.py`'s Protocol; no `src/agents/*` file changed this PBI |
| AC-13 | Provider selection is configuration-driven (`KNOWLEDGE_PROVIDER`), local remains the default, and no endpoint/index/credential is hardcoded | Code review — `src/config/settings.py::KnowledgeSettings`, `src/rag/factory.py`; `pytest` evidence — `tests/unit/rag/test_rag_factory.py` |
| AC-14 | Entra ID (`DefaultAzureCredential`) is the default auth path; API-key auth, if enabled, is read only via `SecretProvider`, never `os.environ` | `pytest` evidence — `tests/unit/rag/test_azure_ai_search_provider.py::test_default_auth_uses_entra_id_not_secret_provider`, `::test_api_key_auth_uses_secret_provider_not_environment` |
| AC-15 | Azure/provider failures (auth, timeout/connectivity, generic HTTP) are normalized into typed `Knowledge*` exceptions, never a raw SDK exception | `pytest` evidence — `tests/unit/rag/test_azure_ai_search_provider.py::test_authentication_failure_raises_knowledge_provider_error`, `::test_service_request_error_raises_knowledge_timeout_error`, `::test_generic_http_response_error_raises_knowledge_provider_error` |
| AC-16 | `AzureAISearchProvider` is fully mocked in its own tests — never called against real Azure | Code review + `pytest` evidence — `tests/unit/rag/test_azure_ai_search_provider.py` (13 tests, all `@patch`-mocked) |
| AC-17 | A reusable Bicep module provisions the Azure AI Search service (RBAC-only, conservative Free-tier default), wired into `main.bicep` and all 3 environment parameter files, with no deployment performed | `az bicep build`/`build-params` evidence — all exit 0, 0 errors, 0 warnings |

## Dependencies

- Everything established in Sprint 01: Supervisor, Tool/Prompt/LLM frameworks, ClaimsAgent,
  BrokerAgent, CommercialIntakeAgent, `POST /chat`, `apps/api/src/api/dependencies.py`.
- PBI-02-01's Knowledge/RAG framework (`src/rag/`).

## Risks

| Risk | Probability | Impact | Mitigation |
|---|---:|---:|---|
| `data/raw/*` is gitignored ("Sensitive or real business data") and would have silently swallowed the synthetic knowledge base | Realized | Media | Caught during validation; relocated to `configs/knowledge_base/` (curated, versioned reference content — the better semantic fit, mirroring `configs/prompts/`) before it could reach a commit. See `decisions.md`. |
| Azure AI Search Free tier allows only one free service per subscription | Low (not deployed) | Low | `dev.bicepparam` uses Free; `staging`/`prod` use Basic specifically to avoid this constraint. See `decisions.md`. |

## Deliverable Log

<!-- Append entries. Do not remove previous entries. -->

PBI-02-01: Reusable Knowledge/RAG framework built (`src/rag/`): `KnowledgeProvider` Protocol, `KnowledgeRetriever` (mirrors `PromptManager`'s "hide the provider, raise typed exceptions on genuine failure" shape), fully typed contracts (`KnowledgeQuery` with Pydantic-validated non-empty `text` and bounded `top_k`, `KnowledgeChunk`, `KnowledgeMetadata`, `KnowledgeResult` with an explicit `has_results` no-results case), and typed exceptions (`KnowledgeError`/`KnowledgeProviderError`). `LocalKnowledgeProvider` performs deterministic keyword-overlap scoring over 5 synthetic Markdown documents (`configs/knowledge_base/`, YAML frontmatter carrying `source_id`/`title`/`category` for future citations) — no embeddings, no vector database, isolated behind the Protocol so a future `AzureAISearchProvider` needs zero change to `KnowledgeRetriever` or any Agent. Integrated into `ClaimsAgent` only (the PBI's "at least one" minimum): `PromptRenderContext` gained an additive `retrieved_knowledge` field (renderer gained a matching `{retrievedKnowledge}` placeholder, exactly mirroring `toolSummaries`), and `ClaimsAgent` retrieves knowledge per turn, threads it into the existing prompt/LLM call as documentary context only, and appends a separate, provable `[knowledge=<source_id>,...]` annotation — retrieved text never touches `ClaimsIntakeState` or the deterministic business-fact text (proven by a dedicated byte-identical-business-text regression test), and retrieval failure degrades gracefully exactly like a Prompt/LLM failure. Zero changes to `src/agents/claims/workflow.py`/`state.py`, `src/supervisor/*`, `ConversationRepository`, or `POST /chat`'s contract — Broker and Commercial Intake are entirely unaffected (no `KnowledgeRetriever` wired to them this PBI). Found and fixed two real, non-Python issues during validation: (1) `data/raw/*` is gitignored for real/sensitive data, which would have silently dropped the knowledge base — relocated to `configs/knowledge_base/`; (2) the API Docker image did not copy the knowledge base directory — fixed the same way PBI-01-03 fixed the equivalent `configs/prompts/` gap. 304/304 tests pass deterministically with no Azure dependency (full Supervisor/Tool/Prompt/LLM/Claims/Broker/Commercial/`/chat` regression suite confirmed passing, clean on the first run modulo one recurring pytest basename collision, fixed the same way as every prior PBI); ruff and mypy clean, clean on the first run; live smoke test confirmed a relevant Claims message produces a `[knowledge=KB-CLAIMS-...]` annotation through the real running API, an unrelated follow-up in the same conversation does not, and Broker/Commercial/Fallback routing are all unaffected. No Azure AI Search, embeddings, vector databases, real documents, RAG evaluation, APIM, authentication, or Azure deployment implemented. — 2026-08-07
Evidence: `docs/sprint_02/evidence/pbi-02-01-knowledge-framework-validation.txt`

PBI-02-02: `AzureAISearchProvider` added (`src/rag/azure_ai_search_provider.py`), a second, production-shaped `KnowledgeProvider` implementing the exact same Protocol as `LocalKnowledgeProvider` — zero changes to `KnowledgeRetriever`, any Agent, or the Protocol itself. Structurally mirrors `AzureOpenAIProvider` (PBI-01-04) exactly: lazy `azure-search-documents`/`azure-identity` imports (never required unless `KNOWLEDGE_PROVIDER=azure_ai_search`), Entra ID (`DefaultAzureCredential`) as the default auth path, API-key auth only via the existing `SecretProvider` abstraction (never `os.environ`), and typed exception mapping (`ClientAuthenticationError`→`KnowledgeProviderError`, `ServiceRequestError`→new `KnowledgeTimeoutError`, generic `HttpResponseError`→`KnowledgeProviderError`, missing endpoint/index at construction→new `KnowledgeConfigurationError`). Plain keyword search only (`search_text=`) — no vector query (the existing `KnowledgeQuery`/`KnowledgeChunk` contract has no embedding fields, so vector search is not required) and no semantic ranker (not justified for a small synthetic corpus); results are mapped from an assumed index schema (`chunk_id`/`content`/`source_id`/`title`/`category`) into the existing typed `KnowledgeChunk`/`KnowledgeMetadata` contracts, preserving citation-ready source metadata. New `src/rag/factory.py` (`get_knowledge_provider`, mirrors `src/llm/factory.py`) and `KnowledgeSettings` (mirrors `LLMSettings`) make provider selection fully configuration-driven; `apps/api/src/api/dependencies.py`'s `get_knowledge_retriever()` routes through the factory with **local unchanged as the default** — verified by running the full regression suite immediately after this wiring change, before writing any Azure AI Search code. New reusable `ops/bicep/modules/ai-search.bicep` module (RBAC-only via the built-in "Search Index Data Reader" role on the shared Managed Identity, Free-tier default for dev — conservative and $0, appropriate since this PBI explicitly excludes semantic ranking/ingestion which Free doesn't support anyway; Basic for staging/prod to avoid the one-free-service-per-subscription constraint), wired into `main.bicep` (new `aiSearchSkuName` param + 3 new outputs) and all 3 environment parameter files — no index, no ingestion, no deployment. Replaced the dead, never-wired Sprint-0 `ENABLE_RAG` placeholder in `.env.example` with the real `KNOWLEDGE_PROVIDER`/`AZURE_AI_SEARCH_*` variables it was always meant to become. 320/320 tests pass deterministically with no Azure dependency (full Supervisor/Tool/Prompt/LLM/Claims/Broker/Commercial/RAG/`/chat` regression suite confirmed passing, one recurring pytest basename collision fixed the same way as every prior PBI); ruff and mypy clean; all 11 Bicep files (`main.bicep` + 10 modules) and all 3 parameter files compile with `az bicep build`/`build-params` at exit 0, 0 errors, 0 warnings; live local smoke test confirmed `KNOWLEDGE_PROVIDER` defaults to local with zero behavior change (`[knowledge=KB-CLAIMS-...]` annotation still produced with zero Azure connectivity) and Broker/Commercial/Fallback remain unaffected. No embeddings, vector databases, semantic ranking, RAG index/ingestion, real documents, citations UI, RAG evaluation, APIM, authentication, or Azure deployment implemented. — 2026-08-07
Evidence: `docs/sprint_02/evidence/pbi-02-02-azure-ai-search-provider-validation.txt`

## Sprint validation

See `validation.md`.

## Sprint retrospective

Complete when closing the sprint:

- What worked:
- What did not:
- Technical debt:
- Security findings:
- Follow-up PBIs:

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

## Out of scope

- Azure AI Search, embeddings, vector databases.
- Real company/customer documents.
- RAG evaluation/quality metrics.
- APIM, authentication, Azure deployment.
- Integrating Knowledge retrieval into Broker or Commercial Intake (deferred — only one agent
  was required this PBI; see `decisions.md`).

## Deliverables

- [x] PBI-02-01: Build the reusable Knowledge / RAG Framework.

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

## Dependencies

- Everything established in Sprint 01: Supervisor, Tool/Prompt/LLM frameworks, ClaimsAgent,
  BrokerAgent, CommercialIntakeAgent, `POST /chat`, `apps/api/src/api/dependencies.py`.

## Risks

| Risk | Probability | Impact | Mitigation |
|---|---:|---:|---|
| `data/raw/*` is gitignored ("Sensitive or real business data") and would have silently swallowed the synthetic knowledge base | Realized | Media | Caught during validation; relocated to `configs/knowledge_base/` (curated, versioned reference content — the better semantic fit, mirroring `configs/prompts/`) before it could reach a commit. See `decisions.md`. |

## Deliverable Log

<!-- Append entries. Do not remove previous entries. -->

PBI-02-01: Reusable Knowledge/RAG framework built (`src/rag/`): `KnowledgeProvider` Protocol, `KnowledgeRetriever` (mirrors `PromptManager`'s "hide the provider, raise typed exceptions on genuine failure" shape), fully typed contracts (`KnowledgeQuery` with Pydantic-validated non-empty `text` and bounded `top_k`, `KnowledgeChunk`, `KnowledgeMetadata`, `KnowledgeResult` with an explicit `has_results` no-results case), and typed exceptions (`KnowledgeError`/`KnowledgeProviderError`). `LocalKnowledgeProvider` performs deterministic keyword-overlap scoring over 5 synthetic Markdown documents (`configs/knowledge_base/`, YAML frontmatter carrying `source_id`/`title`/`category` for future citations) — no embeddings, no vector database, isolated behind the Protocol so a future `AzureAISearchProvider` needs zero change to `KnowledgeRetriever` or any Agent. Integrated into `ClaimsAgent` only (the PBI's "at least one" minimum): `PromptRenderContext` gained an additive `retrieved_knowledge` field (renderer gained a matching `{retrievedKnowledge}` placeholder, exactly mirroring `toolSummaries`), and `ClaimsAgent` retrieves knowledge per turn, threads it into the existing prompt/LLM call as documentary context only, and appends a separate, provable `[knowledge=<source_id>,...]` annotation — retrieved text never touches `ClaimsIntakeState` or the deterministic business-fact text (proven by a dedicated byte-identical-business-text regression test), and retrieval failure degrades gracefully exactly like a Prompt/LLM failure. Zero changes to `src/agents/claims/workflow.py`/`state.py`, `src/supervisor/*`, `ConversationRepository`, or `POST /chat`'s contract — Broker and Commercial Intake are entirely unaffected (no `KnowledgeRetriever` wired to them this PBI). Found and fixed two real, non-Python issues during validation: (1) `data/raw/*` is gitignored for real/sensitive data, which would have silently dropped the knowledge base — relocated to `configs/knowledge_base/`; (2) the API Docker image did not copy the knowledge base directory — fixed the same way PBI-01-03 fixed the equivalent `configs/prompts/` gap. 304/304 tests pass deterministically with no Azure dependency (full Supervisor/Tool/Prompt/LLM/Claims/Broker/Commercial/`/chat` regression suite confirmed passing, clean on the first run modulo one recurring pytest basename collision, fixed the same way as every prior PBI); ruff and mypy clean, clean on the first run; live smoke test confirmed a relevant Claims message produces a `[knowledge=KB-CLAIMS-...]` annotation through the real running API, an unrelated follow-up in the same conversation does not, and Broker/Commercial/Fallback routing are all unaffected. No Azure AI Search, embeddings, vector databases, real documents, RAG evaluation, APIM, authentication, or Azure deployment implemented. — 2026-08-07
Evidence: `docs/sprint_02/evidence/pbi-02-01-knowledge-framework-validation.txt`

## Sprint validation

See `validation.md`.

## Sprint retrospective

Complete when closing the sprint:

- What worked:
- What did not:
- Technical debt:
- Security findings:
- Follow-up PBIs:

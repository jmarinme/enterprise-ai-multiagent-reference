# Sprint 02 Decisions and Deviations

Record sprint-specific decisions and deviations. Cross-sprint decisions belong in ADRs.

## 2026-08-07 — PBI-02-01: `src/rag/` is the CLAUDE.md-reserved package name, typed classes use the PBI's requested "Knowledge*" naming

**Decision:** CLAUDE.md §6 already reserves `src/rag/` ("contains retrieval logic only") as the top-level package for this framework — so the module lives there, not in a newly-invented `src/knowledge/`. The PBI's own requested class names (`KnowledgeProvider`, `KnowledgeRetriever`, `KnowledgeQuery`, `KnowledgeChunk`, `KnowledgeResult`, `KnowledgeMetadata`) are used as-is inside that package. Concrete providers (`LocalKnowledgeProvider` now, a future `AzureAISearchProvider`) live directly in `src/rag/`, not a separate `src/services/rag/` split — matching the precedent already set by `src/prompts/` and `src/llm/` (concrete `FileSystemPromptProvider`/`MockLLMProvider`/`AzureOpenAIProvider` all live alongside their framework, unlike the Tool framework's `src/tools/` vs. `src/services/tools/` split).

**Deviation/status change:** None — a direct application of CLAUDE.md's own repository structure.

**How to apply:** Any future concrete `KnowledgeProvider` (e.g. an Azure AI Search-backed one) should be added directly under `src/rag/`, consistent with the Prompt/LLM precedent, not under `src/services/`.

## 2026-08-07 — PBI-02-01: knowledge base relocated from `data/raw/knowledge_base/` to `configs/knowledge_base/` — a gitignore collision, same class as PBI-01-02's `secrets/` lesson

**Decision:** The synthetic knowledge base was first built under `data/raw/knowledge_base/`, matching CLAUDE.md §6's description of `data/raw/` as read-only source documents. During validation, `git status` never listed the 5 new Markdown files as untracked — `.gitignore` has a blanket `data/raw/*` rule commented "Sensitive or real business data" (only `.gitkeep` is allow-listed through), which was silently swallowing them. This is the same class of issue PBI-01-02's decisions.md already documented for `secrets/` colliding with a same-named source directory. Following that precedent, the knowledge base was relocated to `configs/knowledge_base/` rather than carving an exception into a security-relevant ignore rule — which, on reflection, is also the better semantic fit: these are curated, versioned, synthetic reference documents (frontmatter + body, just like `configs/prompts/`), not raw pipeline input data that happens to need read-only treatment.

**Deviation/status change:** A necessary correction caught during validation, not a deviation from intent — CLAUDE.md's "no real data" requirement is exactly what the ignore rule protects, and synthetic reference documents were never meant to be swept by it, but they were, so they moved. All 9 referencing files (`apps/api/Dockerfile`, `apps/api/src/api/dependencies.py`, and 7 test files) were updated together.

**How to apply:** Anything placed under `data/raw/` must be confirmed with `git status` (or `git check-ignore -v`) before assuming it will be committed — that directory is deliberately swept by `.gitignore` for real-data protection, not merely a suggested location. Curated, versioned, synthetic reference content belongs under `configs/`, alongside prompts.

## 2026-08-07 — PBI-02-01: fixed a Docker packaging gap for `configs/knowledge_base/` — same class as PBI-01-03's `configs/prompts/` fix

**Decision:** `apps/api/Dockerfile` did not copy any knowledge-base directory into the image, so `LocalKnowledgeProvider` would fail to find any document in a deployed container — the exact same gap PBI-01-03 found and fixed for `configs/prompts/`. Fixed identically: `COPY configs/knowledge_base ./configs/knowledge_base`, resolved against `WORKDIR /app` the same way the prompts directory already is.

**Deviation/status change:** A necessary packaging fix, not scope creep — required for this PBI's own deliverable (`ClaimsAgent`'s knowledge retrieval) to actually work in a deployed image, exactly the same justification PBI-01-01's and PBI-01-03's own Docker fixes used.

**How to apply:** Any future top-level content directory a `src/`-package reads via a relative path at runtime (prompts, knowledge base, and so on) must be added to this same `COPY` list — this is now the fourth such directory (`app_src`, `src`, `configs/prompts`, `configs/knowledge_base`) and a good candidate to consolidate into a single `COPY configs ./configs` once a fifth appears, rather than one line per directory.

## 2026-08-07 — PBI-02-01: only `ClaimsAgent` integrates `KnowledgeRetriever` this PBI

**Decision:** The PBI requires integration into "at least one existing agent." Only `ClaimsAgent` was wired with a `KnowledgeRetriever`; `BrokerAgent` and `CommercialIntakeAgent` are unchanged. The `[knowledge=...]` response annotation was built as agent-local code in `ClaimsAgent.handle()` (not folded into the shared `src/agents/shared/annotation.py` helper), so Broker/Commercial's existing calls to `annotate_with_prompt_and_llm` needed zero changes.

**Deviation/status change:** None — the PBI's own stated minimum, chosen deliberately to keep this PBI's scope controlled given its size (a new framework plus one integration).

**How to apply:** Extending Broker or Commercial Intake to use `KnowledgeRetriever` is a small, mechanical follow-up (constructor injection + a `_retrieve_knowledge` helper + threading `retrieved_knowledge` into their existing `PromptRenderContext` calls, exactly mirroring `ClaimsAgent`'s pattern) — at that point, revisit whether the retrieval-and-annotate sequence itself has become a third, real, stable duplication worth extracting into `src/agents/shared/`, per the same rule-of-three discipline PBI-01-07 already established.

## 2026-08-07 — PBI-02-01: corrected `test_agent_response_is_stable_when_input_has_no_recognizable_claims_fields`

**Decision:** This test's two probe messages ("first message" / "completely different message") were chosen in PBI-01-05 to have no CLAIMS-field keyword overlap. Once `ClaimsAgent` started retrieving knowledge per-turn, one of the two ("completely different message") turned out to share the word "different" with `KB-COMMERCIAL-0001"s text, producing a `[knowledge=...]` annotation the other message didn't get — breaking the test's "both responses are identical" assertion. This is a genuine, expected new source of input-dependence (retrieval now depends on the full message text, not just recognizable claims fields), the same class of correction PBI-01-04's decisions.md already documented for the LLM-wiring case. Fixed by replacing both probe messages with words guaranteed to have zero overlap with the knowledge base.

**Deviation/status change:** A correct fix to an assumption invalidated by this PBI's own intended behavior change, not a regression.

**How to apply:** Any future PBI that makes `ClaimsAgent`'s (or another RAG-integrated agent's) response depend on more of the input message should expect, and correct, any prior test asserting response identity across differing inputs — check whether the difference is due to genuinely new, intended input-sensitivity before assuming a regression.

## 2026-08-07 — PBI-02-02: no vector search or semantic ranker — plain keyword search only

**Decision:** `AzureAISearchProvider.retrieve()` calls `SearchClient.search(search_text=...)` — Azure AI Search's classic full-text (BM25) keyword search — never a vector query (`VectorizableTextQuery`/vector fields) and never `query_type="semantic"`. Justification: the existing `KnowledgeQuery`/`KnowledgeChunk` contracts (PBI-02-01) have no embedding field anywhere, so the PBI's own "vector search unless already required by the existing contract" test is not met; and semantic ranking has no justification for a five-document synthetic reference corpus where BM25 keyword matching (the same strategy `LocalKnowledgeProvider` already uses) is more than sufficient and keeps behavior comparable between the two providers.

**Deviation/status change:** None — a direct, literal application of both of this PBI's explicit exclusions.

**How to apply:** If a future PBI adds embedding fields to `KnowledgeChunk`/`KnowledgeQuery` (a deliberate, ADR-worthy contract change, not a small addition) and a real ingestion pipeline that populates vector fields, that is the point to add a vector query path to `AzureAISearchProvider` — not before, and not by inferring vector need from `AzureAISearchProvider`'s implementation alone.

## 2026-08-07 — PBI-02-02: assumed Azure AI Search index schema is fixed, not configurable

**Decision:** `AzureAISearchProvider` assumes a specific index schema — key field `chunk_id`, searchable `content`, plus `source_id`/`title`/`category` matching `KnowledgeMetadata`'s own field names — hardcoded as `_SELECT_FIELDS` rather than exposed as configuration. Index creation and document ingestion are explicitly out of scope for this PBI (no index exists yet to disagree with), so there is nothing real to configure against; inventing a field-name-mapping configuration surface now would be speculative.

**Deviation/status change:** None — consistent with CLAUDE.md §7's "do not design for hypothetical future requirements."

**How to apply:** The future PBI that actually creates the Azure AI Search index and ingestion pipeline should treat `_SELECT_FIELDS` in `src/rag/azure_ai_search_provider.py` as the index's required minimum field contract (or update both together) — at that point, if the real index schema needs different field names, revisit whether a configurable field-mapping is actually justified by then, rather than guessing now.

## 2026-08-07 — PBI-02-02: Azure AI Search sizing — Free tier for dev, Basic for staging/prod

**Decision:** `ops/bicep/modules/ai-search.bicep` defaults `skuName` to `'free'`; `dev.bicepparam` uses that default, `staging.bicepparam`/`prod.bicepparam` explicitly override to `'basic'`. Free is the most conservative (cost) choice and is not a crippled trial — its limitations (no semantic ranker, 3-index cap, no SLA, shared compute) are all things this PBI already excludes or doesn't need for a five-document synthetic corpus. Basic (not Free) for staging/prod for two reasons: an Azure subscription gets exactly one Free-tier search service, which would conflict with dev's own use of it; and pre-production/production environments reasonably want an SLA, matching the same "modest headroom" philosophy `staging`/`prod.bicepparam` already apply to every other resource in this template (Standard ACR, larger Container App replica counts, purge protection on).

**Deviation/status change:** None — a direct application of CLAUDE.md's "conservative DEV sizing" instruction, extended consistently to the other two environments using the same reasoning already established by the existing Cosmos DB/ACR/Container App parameter choices.

**How to apply:** If a future environment needs Standard (e.g. a real production workload with real document volume), add it via a parameter override in that environment's `.bicepparam` file only — `main.bicep`'s `@allowed(['free','basic','standard'])` already permits it; no module change needed.

## 2026-08-07 — PBI-02-02: local auth left enabled at the Azure AI Search service (`disableLocalAuth: false`), unlike Cosmos DB's stricter posture

**Decision:** `ai-search.bicep` does not set `disableLocalAuth: true` the way `cosmos-db.bicep` does. This PBI explicitly requires that "if key authentication is supported, retrieve the key only through SecretProvider" remain a real, usable opt-in path for `AzureAISearchProvider` — disabling local (key-based) auth at the service level would make that path impossible to exercise even when deliberately configured. Entra ID (`DefaultAzureCredential` via the granted "Search Index Data Reader" role) remains the default and preferred path in both the Bicep module (RBAC role assignment) and the Python provider (no `secret_provider` configured ⇒ Entra ID).

**Deviation/status change:** A deliberate difference from the Cosmos DB module's posture, not an oversight — Cosmos DB has no PBI requirement for an opt-in key-auth path, so disabling local auth entirely was correct there; this PBI has the opposite explicit requirement.

**How to apply:** If a future ADR decides key-based auth should never be used against this Azure AI Search service in any environment, that is the point to set `disableLocalAuth: true` here too — until then, leaving it enabled at the service level does not itself grant key access to anyone (a key must still be separately generated and placed in Key Vault out of band, which this module does not do).

## 2026-08-07 — PBI-02-03: Grounding lives in `src/rag/`, not a new top-level package

**Decision:** The Grounding & Citations layer (`src/rag/grounding_models.py`, `src/rag/grounder.py`) was added directly inside the existing `src/rag/` package rather than a new `src/grounding/` or similar. It is a direct extension of the same "documentary retrieval" concern CLAUDE.md §6 already scopes `src/rag/` to, and it depends only on `src.rag.models` — creating a separate top-level package would have required CLAUDE.md §6 approval ("do not create a new top-level folder without approval") for no architectural benefit.

**Deviation/status change:** None — a direct application of the same reasoning already recorded for PBI-02-01/02-02 (concrete providers live directly in `src/rag/`, matching the Prompt/LLM precedent).

**How to apply:** Any future retrieval-adjacent concern (re-ranking, evaluation, etc.) that operates purely on `KnowledgeChunk`/`GroundedContext` types should default to living in `src/rag/` too, unless it grows a genuinely separate dependency surface (e.g., its own external service) that would justify a new top-level package.

## 2026-08-07 — PBI-02-03: citations are attached deterministically by the Grounder, not selected by the LLM

**Decision:** `GroundedResponse.citations` (produced by `Grounder.build_response()`) is always set to exactly `GroundedContext.citations` — the full, already-deduplicated/ordered/top-k'd set the Grounder made available — never a subset the LLM call itself determines. This is the mechanism that satisfies "the LLM must never invent a citation": since `MockLLMProvider` is intentionally content-agnostic (PBI-01-04) and cannot genuinely evaluate which retrieved passages it used, allowing the LLM to freely determine the citation list would have no real signal behind it and would be unsafe by construction once a real LLM is wired in without further validation logic.

**Deviation/status change:** None — a direct, literal reading of the PBI's own explicit requirement, resolved architecturally (by construction) rather than by runtime validation of LLM output.

**How to apply:** If a future PBI introduces genuine LLM-driven citation selection (the model choosing a subset of available citations it actually used), that is a deliberate, ADR-worthy contract change to `Grounder.build_response()` — it must still validate that any LLM-selected citation is a subset of `GroundedContext.citations`, never trust a new citation the LLM invents outright.

## 2026-08-07 — PBI-02-03: fully replaced the `[knowledge=...]` text annotation rather than keeping both

**Decision:** PBI-02-01's ad-hoc `[knowledge=<source_id>,...]` response-text annotation in `ClaimsAgent` was completely removed and replaced by the typed `citations`/`grounding_metadata` fields on `AgentResponse`/`ChatResponse`. Keeping both would have been redundant (the same information in two incompatible shapes) and defeats the PBI's own stated goal of "typed citations, no strings containing JSON" — the bracket annotation was exactly the kind of untyped, string-embedded metadata this PBI exists to replace.

**Deviation/status change:** An intentional, in-scope behavior change (not a regression) — `tests/unit/agents/test_claims_agent_knowledge_integration.py` and `tests/unit/api/test_chat.py` were updated accordingly to assert on the new typed fields instead of the removed bracket text, following the same precedent as PBI-02-01's own test correction for `test_agent_response_is_stable_when_input_has_no_recognizable_claims_fields`.

**How to apply:** Any future code or documentation still referencing the `[knowledge=...]` annotation format is stale and should be updated to reference `AgentResponse.citations`/`grounding_metadata` instead.

## 2026-08-07 — PBI-02-03: `GroundingMetadata.is_grounded` is a `computed_field`, not a plain `@property`

**Decision:** `is_grounded` was initially written as a plain `@property`. Before shipping, this was corrected to Pydantic's `@computed_field` decorator (kept alongside `@property`) — a plain property is silently excluded from `model_dump()`/`model_dump_json()`/FastAPI's JSON serialization in Pydantic v2, which would have made `groundingMetadata.isGrounded` invisible on the actual `POST /chat` wire response even though it exists on the Python object, defeating the field's whole purpose ("a caller can tell 'grounded with N sources' ... without inspecting the citations list").

**Deviation/status change:** A correction caught before the live smoke test confirmed the API contract, not a regression — verified by the smoke test's `"groundingMetadata":{"retrievedCount":2,"citationCount":2,"topK":2,"isGrounded":true}` output.

**How to apply:** Any future derived/computed field on a Pydantic model that must appear in JSON output (API responses, persisted documents) needs `@computed_field`, not a plain `@property` — a plain property is fine only for internal-Python-only convenience accessors that never cross a serialization boundary.

## 2026-08-07 — PBI-02-03: only `ClaimsAgent` integrates the Grounder this PBI

**Decision:** Consistent with PBI-02-01's own scope decision (only `ClaimsAgent` was wired with a `KnowledgeRetriever`), only `ClaimsAgent` was wired with a `Grounder` this PBI. `BrokerAgent` and `CommercialIntakeAgent` are unchanged — they never had `KnowledgeRetriever` injected in the first place, so there is nothing yet for a `Grounder` to ground for them.

**Deviation/status change:** None — the natural consequence of PBI-02-01's already-recorded scope decision, not a new deviation.

**How to apply:** If/when a future PBI extends `KnowledgeRetriever` to Broker or Commercial Intake (per PBI-02-01's own follow-up note), wiring a `Grounder` into that same agent at the same time is a small, mechanical addition — constructor injection plus the same `ground()`/`build_response()` call sequence `ClaimsAgent.handle()` already demonstrates.

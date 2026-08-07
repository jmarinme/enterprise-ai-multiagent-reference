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

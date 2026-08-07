# Sprint 02 Implementation Plan

## PBI-02-01 — Knowledge / RAG Framework

Builds `src/rag/` (Protocol + typed contracts + `KnowledgeRetriever` + deterministic
`LocalKnowledgeProvider`) behind the same interface-only shape already proven by the
Supervisor/Tool/Prompt/LLM frameworks (Sprint 01), then wires it into `ClaimsAgent` via
constructor injection. No agent's business workflow (state machine, extraction, Tool calls) is
rewritten — knowledge only reaches the existing `PromptManager`/`LLMProvider` call as an
additive `retrieved_knowledge` field on `PromptRenderContext`. See `docs/sprint_02/decisions.md`
for the `data/raw/` → `configs/knowledge_base/` relocation (a gitignore collision, same class
of issue as PBI-01-02's `secrets/` lesson) and the Docker packaging fix (same class of issue as
PBI-01-03's `configs/prompts/` packaging fix).

## PBI-02-02 — Azure AI Search KnowledgeProvider

Adds `AzureAISearchProvider` (`src/rag/azure_ai_search_provider.py`) as a second
`KnowledgeProvider` implementation, structurally mirroring `AzureOpenAIProvider`'s proven shape
(PBI-01-04) exactly: lazy SDK imports, Entra ID default auth, `SecretProvider`-only API-key
opt-in, typed exception mapping. Provider selection becomes configuration-driven via a new
`KnowledgeSettings` (mirrors `LLMSettings`) and `src/rag/factory.py` (mirrors
`src/llm/factory.py`) — local remains the default, verified behavior-preserving by running the
full regression suite immediately after the `dependencies.py` wiring change, before writing any
Azure AI Search code. A new reusable `ops/bicep/modules/ai-search.bicep` module provisions the
search *service* only (RBAC-only, Free-tier dev default) — no index, no ingestion, no
deployment. See `docs/sprint_02/decisions.md` for the Free-vs-Basic tier reasoning per
environment and why vector search/semantic ranking were not implemented.

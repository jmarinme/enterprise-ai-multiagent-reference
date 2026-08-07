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

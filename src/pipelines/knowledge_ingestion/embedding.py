"""Embedding pipeline abstraction (PBI-03-03).

Deliberately an abstraction only: no vector field exists on the index schema
(src.pipelines.knowledge_ingestion.index_schema) and no real embedding model is called anywhere
in this codebase — every prior RAG PBI (PBI-02-01, PBI-02-02) explicitly excluded vector search
as unjustified for this small, synthetic reference corpus, and that exclusion still holds here.

What this module DOES provide: a stable seam (the EmbeddingProvider Protocol) the ingestion
pipeline already calls on every chunk, so that wiring in a real embedding model in a future PBI
is a one-line composition-root change (swap NullEmbeddingProvider for a concrete
implementation) — no change to KnowledgeIngestionPipeline, IngestionChunk, or the index schema's
non-vector fields would be required. IngestionChunk.embedding already exists and simply stays
None until that future PBI both implements a real provider AND extends the index schema with a
vector field + vectorSearch configuration.
"""

from __future__ import annotations

from typing import Protocol


class EmbeddingProvider(Protocol):
    """Contract for producing a vector embedding for one chunk of text."""

    async def embed(self, text: str) -> list[float] | None: ...


class NullEmbeddingProvider:
    """Default EmbeddingProvider: always returns None. Used by KnowledgeIngestionPipeline
    unless a real embedding provider is explicitly injected — matching this platform's
    consistent "typed abstraction now, real implementation only when justified" pattern
    (see src.llm.provider.LLMProvider / src.rag.provider.KnowledgeProvider for the same shape
    applied to other frameworks)."""

    async def embed(self, text: str) -> list[float] | None:
        return None

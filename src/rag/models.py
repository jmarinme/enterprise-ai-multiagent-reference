"""Typed contracts for the Knowledge/RAG retrieval framework (PBI-02-01).

Agent -> KnowledgeRetriever -> KnowledgeProvider -> KnowledgeResult -> PromptManager ->
LLMProvider. No raw untyped dict crosses any of these boundaries.

RAG is documentary only (CLAUDE.md §4.4): retrieved chunks are reference/contextual
information for the LLM, never a substitute for a Tool-sourced business fact.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class KnowledgeMetadata(BaseModel):
    """Descriptive metadata for a retrievable knowledge document, independent of any one
    retrieved chunk. Carries exactly what CLAUDE.md §4.4 requires every RAG result to provide:
    source identification sufficient for a citation (PBI-02-03's Grounding layer, src.rag.
    grounder, treats source_id as the citation's document id).

    section/source_path are additive (PBI-02-03), optional, and default to None: a provider
    that has no sub-document structure or no filesystem-style path (e.g. a future Azure AI
    Search index without those fields populated yet) simply omits them — the Grounding layer
    still produces a valid Citation either way."""

    source_id: str
    title: str
    category: str
    section: str | None = None
    source_path: str | None = None


class KnowledgeChunk(BaseModel):
    """One retrieved passage of text plus the metadata needed to cite it and the score it was
    ranked with for a specific query. score is contextual (assigned at retrieval time), not a
    fixed property of the underlying document."""

    chunk_id: str
    text: str
    metadata: KnowledgeMetadata
    score: float = 0.0


class KnowledgeQuery(BaseModel):
    """A typed retrieval request. text must be non-empty and top_k must be a positive, bounded
    integer — both enforced by Pydantic at construction time, so an invalid query never reaches
    a KnowledgeProvider."""

    text: str = Field(min_length=1)
    top_k: int = Field(default=3, gt=0, le=20)
    category: str | None = None


class KnowledgeResult(BaseModel):
    """The typed outcome of a retrieval. An empty chunks list is the explicit, legitimate
    "no results" case — never None, never an exception, for a query that simply has no
    relevant match."""

    query: KnowledgeQuery
    chunks: list[KnowledgeChunk] = Field(default_factory=list)

    @property
    def has_results(self) -> bool:
        return len(self.chunks) > 0

"""Grounder: the reusable Grounding layer (PBI-02-03) sitting between KnowledgeRetriever and
PromptManager. Converts raw, possibly duplicate, unordered KnowledgeChunks into a deterministic,
deduplicated, top-k GroundedContext with typed Citations.

Provider-agnostic by construction: this module imports only src.rag.models (the shared
KnowledgeChunk/KnowledgeMetadata contract) and src.rag.grounding_models — never
LocalKnowledgeProvider or AzureAISearchProvider — so grounding behaves identically no matter
which KnowledgeProvider produced the chunks.

Stateless (no constructor configuration yet): implemented as a class, not a bare function,
purely for consistency with the rest of this codebase's injected-component style
(ToolExecutor, PromptManager, KnowledgeRetriever) and to keep it trivially mockable in Agent
tests — not because it needs to hold state.
"""

from __future__ import annotations

from src.rag.grounding_models import (
    Citation,
    CitationReference,
    GroundedContext,
    GroundedResponse,
    GroundingMetadata,
)
from src.rag.models import KnowledgeChunk


class Grounder:
    """Deduplicates, deterministically orders, and caps retrieved KnowledgeChunks into a typed
    GroundedContext, then wraps a response's text with the resulting citations."""

    def ground(self, chunks: list[KnowledgeChunk], top_k: int) -> GroundedContext:
        """top_k here is independent of whatever top_k was used at retrieval time — a caller
        may retrieve more chunks than it ultimately wants to cite."""
        retrieved_count = len(chunks)
        deduplicated = self._deduplicate(chunks)
        ordered = sorted(deduplicated, key=lambda chunk: (-chunk.score, chunk.chunk_id))
        top = ordered[:top_k]

        citations = [
            Citation(
                reference=CitationReference(reference_id=str(index + 1), chunk_id=chunk.chunk_id),
                document_id=chunk.metadata.source_id,
                title=chunk.metadata.title,
                section=chunk.metadata.section,
                source_path=chunk.metadata.source_path,
                score=chunk.score,
            )
            for index, chunk in enumerate(top)
        ]
        context_text = "\n".join(
            f"[{citation.reference.reference_id}] {chunk.text}"
            for citation, chunk in zip(citations, top, strict=True)
        )

        return GroundedContext(
            context_text=context_text,
            citations=citations,
            metadata=GroundingMetadata(
                retrieved_count=retrieved_count,
                citation_count=len(citations),
                top_k=top_k,
            ),
        )

    def build_response(self, text: str, grounded_context: GroundedContext) -> GroundedResponse:
        """Attaches exactly the citations grounded_context made available — never a citation
        beyond that set, since MockLLMProvider (and any LLMProvider, per this Agent's design)
        never determines the citation list itself. This is what guarantees "the LLM must never
        invent a citation" (CLAUDE.md §4.4) by construction rather than by post-hoc validation."""
        return GroundedResponse(text=text, citations=grounded_context.citations)

    @staticmethod
    def _deduplicate(chunks: list[KnowledgeChunk]) -> list[KnowledgeChunk]:
        """Removes duplicate chunk_ids, keeping the first occurrence — deterministic and
        order-preserving. Duplicates can arise when a caller combines results from more than
        one retrieval call before grounding; a single KnowledgeProvider.retrieve() call never
        returns the same chunk_id twice on its own."""
        seen: set[str] = set()
        unique: list[KnowledgeChunk] = []
        for chunk in chunks:
            if chunk.chunk_id not in seen:
                seen.add(chunk.chunk_id)
                unique.append(chunk)
        return unique

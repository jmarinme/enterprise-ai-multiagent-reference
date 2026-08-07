"""Typed contracts for the Grounding & Citations layer (PBI-02-03), extending the Knowledge/RAG
framework (PBI-02-01/02-02).

New flow: KnowledgeRetriever -> KnowledgeChunk(s) -> Grounder (src.rag.grounder) ->
GroundedContext -> PromptManager -> LLMProvider -> GroundedResponse.

The LLM must never invent a citation (CLAUDE.md §4.4): GroundedResponse.citations is always a
subset of (in this PBI's deterministic design, always exactly equal to) the citations the
Grounder made available in GroundedContext — never a new set the LLM call itself produces. See
src.rag.grounder for why.

No raw dict, no JSON-encoded string, crosses any of these boundaries — every field here is a
typed Pydantic attribute.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, computed_field
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    """Citations are nested inside the transport-layer API response (POST /chat), so — like
    src.domain.conversation's models — they serialize with camelCase field names on the wire,
    matching this API's existing convention (conversationId, userId, ...)."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class CitationReference(_CamelModel):
    """A stable, deterministic ordinal ("1", "2", ...) correlating an inline citation marker
    in grounded context text with a specific Citation, without repeating that citation's own
    metadata. Assigned by the Grounder in the same deterministic order as the citations list
    itself — reference_id "1" is always citations[0], etc."""

    reference_id: str
    chunk_id: str


class Citation(_CamelModel):
    """One typed citation: everything needed to identify and later render a reference to a
    retrieved knowledge chunk. Preserves every field this PBI requires: document id (the
    source document's own identifier — KnowledgeMetadata.source_id), section, score, title,
    and source path."""

    reference: CitationReference
    document_id: str
    title: str
    section: str | None = None
    source_path: str | None = None
    score: float


class GroundingMetadata(_CamelModel):
    """Summary of a single grounding pass: how many chunks came back from retrieval versus how
    many became citations (after deduplication and top-k), so a caller can tell "grounded with
    N sources" from "nothing relevant was found" without inspecting the citations list."""

    retrieved_count: int
    citation_count: int
    top_k: int

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_grounded(self) -> bool:
        """Serialized (unlike a plain @property) so API callers can read it directly off the
        JSON response without re-deriving it from citation_count."""
        return self.citation_count > 0


class GroundedContext(BaseModel):
    """The Grounding layer's output, handed to the existing PromptManager/LLM call in place of
    a raw list[str] of chunk texts: deduplicated, deterministically ordered, top-k'd citations,
    plus context_text — the same information formatted as numbered passages
    ("[1] ...", "[2] ...") a prompt template can render via {retrievedKnowledge}.

    Internal-only (never serialized directly to the API) — hence plain BaseModel rather than
    _CamelModel, unlike Citation/GroundingMetadata which travel all the way to POST /chat."""

    context_text: str
    citations: list[Citation] = Field(default_factory=list)
    metadata: GroundingMetadata


class GroundedResponse(BaseModel):
    """The final grounded output: the deterministic response text plus the exact citations
    that were made available to produce it. Internal-only, same reasoning as GroundedContext —
    an Agent unpacks this into its own typed AgentResponse fields."""

    text: str
    citations: list[Citation] = Field(default_factory=list)

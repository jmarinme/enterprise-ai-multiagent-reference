"""Typed contracts for the knowledge ingestion pipeline (PBI-03-03).

IngestionChunk is the ingestion-side counterpart to src.rag.models.KnowledgeChunk: the same
document identity/section/source-path fields Grounding (PBI-02-03) needs for a Citation, plus
ingestion-only concerns (version, content_hash, an optional embedding) that never cross into
the retrieval-side KnowledgeChunk contract at all.
"""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, Field, computed_field


class IngestionChunk(BaseModel):
    """One chunk produced by a DocumentLoader, ready to be mapped onto an Azure AI Search
    document and uploaded. Field names here are deliberately identical to
    src.rag.models.KnowledgeMetadata's (source_id, title, category, section, source_path) and
    to AzureAISearchProvider._SELECT_FIELDS — the same names flow unchanged from ingestion
    through the index to retrieval, so Grounding stays compatible by construction, not by
    convention alone.
    """

    chunk_id: str
    source_id: str
    title: str
    category: str
    text: str
    section: str | None = None
    source_path: str
    version: str = "1.0.0"
    embedding: list[float] | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def content_hash(self) -> str:
        """Deterministic SHA-256 of text — the single signal incremental ingestion uses to
        decide "unchanged, skip" vs. "changed, upload". Always derived from text (a
        computed_field, not a plain @property, so it actually serializes — see
        docs/sprint_02/decisions.md's GroundingMetadata.is_grounded precedent for why a plain
        @property would silently be dropped from JSON/dict output)."""
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


class IngestionReport(BaseModel):
    """The outcome of one KnowledgeIngestionPipeline.ingest() run: which chunk_ids were
    uploaded (new or changed), left unchanged (content_hash matched what the index already
    had), deleted (present in the index but no longer produced by any loader), or failed."""

    index_name: str
    uploaded_chunk_ids: list[str] = Field(default_factory=list)
    unchanged_chunk_ids: list[str] = Field(default_factory=list)
    deleted_chunk_ids: list[str] = Field(default_factory=list)
    failed: dict[str, str] = Field(default_factory=dict)

    @property
    def total_processed(self) -> int:
        return len(self.uploaded_chunk_ids) + len(self.unchanged_chunk_ids)

    @property
    def has_failures(self) -> bool:
        return len(self.failed) > 0

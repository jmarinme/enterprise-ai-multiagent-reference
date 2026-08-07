"""KnowledgeIngestionPipeline (PBI-03-03): the orchestrator tying loaders, the index schema,
and Azure AI Search's data/management planes together.

Ensure index -> load documents via registered DocumentLoaders -> compute content_hash per
chunk -> diff against what the index already has -> upload new/changed chunks
(merge_or_upload, so a partial index is never wiped), skip unchanged chunks, delete chunks
whose source document no longer exists.

Client construction (SearchIndexClient/SearchClient, and their Managed-Identity-vs-API-key
auth) deliberately happens OUTSIDE this class — the same dependency-injection pattern every
other framework in this codebase uses (ToolExecutor takes a ToolRegistry, ToolCallingOrchestrator
takes a ToolExecutor). See ops/scripts/ingest_knowledge_base.py for the composition root that
builds these clients from src.config.settings.KnowledgeSettings, exactly as
src.rag.azure_ai_search_provider.AzureAISearchProvider._get_client already does for retrieval —
this pipeline never duplicates that auth logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from azure.core.exceptions import HttpResponseError

from src.pipelines.knowledge_ingestion.embedding import EmbeddingProvider, NullEmbeddingProvider
from src.pipelines.knowledge_ingestion.exceptions import IndexOperationError, IngestionError
from src.pipelines.knowledge_ingestion.index_schema import (
    CHUNK_ID_FIELD,
    CONTENT_HASH_FIELD,
    build_index_definition,
    chunk_to_search_document,
)
from src.pipelines.knowledge_ingestion.models import IngestionChunk, IngestionReport

if TYPE_CHECKING:
    from collections.abc import Sequence

    from azure.search.documents.aio import SearchClient
    from azure.search.documents.indexes.aio import SearchIndexClient

    from src.pipelines.knowledge_ingestion.loaders import DocumentLoader


class KnowledgeIngestionPipeline:
    """Builds/updates the Azure AI Search index schema and performs incremental,
    delete-aware document ingestion. index_name is always the caller-supplied, configured
    value (src.config.settings.KnowledgeSettings.azure_ai_search_index_name) — never a
    literal anywhere in this class."""

    def __init__(
        self,
        index_client: SearchIndexClient,
        search_client: SearchClient,
        index_name: str,
        loaders: Sequence[DocumentLoader],
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._index_client = index_client
        self._search_client = search_client
        self._index_name = index_name
        self._loaders = list(loaders)
        self._embedding_provider = embedding_provider or NullEmbeddingProvider()

    async def ensure_index(self) -> None:
        """Creates the index if it does not exist, or updates its schema in place if it does.
        Safe to call on every ingestion run — idempotent, matching Azure AI Search's own
        create_or_update_index semantics."""
        try:
            await self._index_client.create_or_update_index(build_index_definition(self._index_name))
        except HttpResponseError as exc:
            raise IndexOperationError("ensure_index", str(exc)) from exc

    async def ingest(self, documents_root: Path) -> IngestionReport:
        """Loads every supported document under documents_root, uploads new/changed chunks,
        skips unchanged ones, and deletes index documents whose source chunk no longer
        exists. A single malformed source document fails that document only (recorded in the
        report) — it never aborts ingestion of the rest."""
        chunks, load_failures = self._load_all(documents_root)
        for chunk in chunks:
            chunk.embedding = await self._embedding_provider.embed(chunk.text)

        existing_hashes = await self._existing_content_hashes()

        to_upload = [
            chunk for chunk in chunks if existing_hashes.get(chunk.chunk_id) != chunk.content_hash
        ]
        unchanged_ids = [
            chunk.chunk_id
            for chunk in chunks
            if existing_hashes.get(chunk.chunk_id) == chunk.content_hash
        ]

        uploaded_ids, upload_failures = await self._upload(to_upload)
        deleted_ids = await self._delete_stale(existing_hashes, current_ids={c.chunk_id for c in chunks})

        return IngestionReport(
            index_name=self._index_name,
            uploaded_chunk_ids=uploaded_ids,
            unchanged_chunk_ids=unchanged_ids,
            deleted_chunk_ids=deleted_ids,
            failed={**load_failures, **upload_failures},
        )

    def _load_all(self, documents_root: Path) -> tuple[list[IngestionChunk], dict[str, str]]:
        chunks: list[IngestionChunk] = []
        failures: dict[str, str] = {}
        for path in sorted(p for p in documents_root.iterdir() if p.is_file()):
            loader = next((candidate for candidate in self._loaders if candidate.matches(path)), None)
            if loader is None:
                continue
            try:
                chunks.extend(loader.load(path))
            except IngestionError as exc:
                failures[str(path)] = str(exc)
        return chunks, failures

    async def _existing_content_hashes(self) -> dict[str, str]:
        try:
            pages = await self._search_client.search(
                search_text="*", select=[CHUNK_ID_FIELD, CONTENT_HASH_FIELD]
            )
            return {item[CHUNK_ID_FIELD]: item.get(CONTENT_HASH_FIELD, "") async for item in pages}
        except HttpResponseError as exc:
            raise IndexOperationError("list_existing", str(exc)) from exc

    async def _upload(self, chunks: list[IngestionChunk]) -> tuple[list[str], dict[str, str]]:
        if not chunks:
            return [], {}
        documents = [chunk_to_search_document(chunk) for chunk in chunks]
        try:
            results = await self._search_client.merge_or_upload_documents(documents=documents)
        except HttpResponseError as exc:
            raise IndexOperationError("upload", str(exc)) from exc

        uploaded_ids: list[str] = []
        failures: dict[str, str] = {}
        for chunk, result in zip(chunks, results, strict=True):
            if result.succeeded:
                uploaded_ids.append(chunk.chunk_id)
            else:
                failures[chunk.chunk_id] = result.error_message or "upload failed"
        return uploaded_ids, failures

    async def _delete_stale(self, existing_hashes: dict[str, str], current_ids: set[str]) -> list[str]:
        stale_ids = sorted(set(existing_hashes) - current_ids)
        if not stale_ids:
            return []
        try:
            await self._search_client.delete_documents(
                documents=[{CHUNK_ID_FIELD: chunk_id} for chunk_id in stale_ids]
            )
        except HttpResponseError as exc:
            raise IndexOperationError("delete", str(exc)) from exc
        return stale_ids

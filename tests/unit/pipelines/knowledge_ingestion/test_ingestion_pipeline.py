"""Unit tests for KnowledgeIngestionPipeline (PBI-03-03), fully mocked — no real Azure AI
Search connectivity anywhere. Covers ensure_index, incremental ingestion (new/unchanged/
deleted), per-document load failures, per-document upload failures, and embedding-provider
wiring.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from src.pipelines.knowledge_ingestion.embedding import EmbeddingProvider
from src.pipelines.knowledge_ingestion.models import IngestionChunk
from src.pipelines.knowledge_ingestion.pipeline import KnowledgeIngestionPipeline


async def _async_iter(items: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    for item in items:
        yield item


class _FakeIndexingResult:
    def __init__(self, key: str, succeeded: bool, error_message: str | None = None) -> None:
        self.key = key
        self.succeeded = succeeded
        self.error_message = error_message


class _StubLoader:
    """Returns preset chunks (or raises a preset exception) keyed by filename — gives each
    test full control over exactly what the pipeline sees without needing real files."""

    def __init__(self, mapping: dict[str, list[IngestionChunk] | Exception]) -> None:
        self._mapping = mapping

    def matches(self, path: Path) -> bool:
        return path.name in self._mapping

    def load(self, path: Path) -> list[IngestionChunk]:
        result = self._mapping[path.name]
        if isinstance(result, Exception):
            raise result
        return result


class _RecordingEmbeddingProvider:
    def __init__(self) -> None:
        self.embedded_texts: list[str] = []

    async def embed(self, text: str) -> list[float] | None:
        self.embedded_texts.append(text)
        return [0.1, 0.2]


def _chunk(chunk_id: str, text: str = "body text") -> IngestionChunk:
    return IngestionChunk(
        chunk_id=chunk_id,
        source_id=chunk_id,
        title="Title",
        category="test",
        text=text,
        source_path=f"configs/knowledge_base/{chunk_id}.md",
    )


def _build_pipeline(
    loaders: list[Any],
    search_results: list[dict[str, Any]] | None = None,
    upload_results: list[_FakeIndexingResult] | None = None,
    embedding_provider: EmbeddingProvider | None = None,
) -> tuple[KnowledgeIngestionPipeline, MagicMock, MagicMock]:
    index_client = MagicMock()
    index_client.create_or_update_index = AsyncMock()

    search_client = MagicMock()
    search_client.search = AsyncMock(return_value=_async_iter(search_results or []))
    search_client.merge_or_upload_documents = AsyncMock(return_value=upload_results or [])
    search_client.delete_documents = AsyncMock()

    pipeline = KnowledgeIngestionPipeline(
        index_client=index_client,
        search_client=search_client,
        index_name="tmxai-knowledge-index",
        loaders=loaders,
        embedding_provider=embedding_provider,
    )
    return pipeline, index_client, search_client


async def test_ensure_index_creates_or_updates_the_configured_index() -> None:
    pipeline, index_client, _ = _build_pipeline(loaders=[])

    await pipeline.ensure_index()

    index_client.create_or_update_index.assert_called_once()
    (index_arg,), _ = index_client.create_or_update_index.call_args
    assert index_arg.name == "tmxai-knowledge-index"


async def test_ingest_uploads_new_chunks_when_the_index_is_empty(tmp_path: Path) -> None:
    (tmp_path / "doc.md").write_text("irrelevant", encoding="utf-8")
    chunk = _chunk("KB-NEW-0001")
    loader = _StubLoader({"doc.md": [chunk]})
    pipeline, _, search_client = _build_pipeline(
        loaders=[loader],
        search_results=[],
        upload_results=[_FakeIndexingResult(key=chunk.chunk_id, succeeded=True)],
    )

    report = await pipeline.ingest(tmp_path)

    assert report.uploaded_chunk_ids == ["KB-NEW-0001"]
    assert report.unchanged_chunk_ids == []
    assert report.deleted_chunk_ids == []
    assert report.failed == {}
    search_client.merge_or_upload_documents.assert_called_once()


async def test_ingest_skips_unchanged_chunks(tmp_path: Path) -> None:
    (tmp_path / "doc.md").write_text("irrelevant", encoding="utf-8")
    chunk = _chunk("KB-SAME-0001", text="unchanged body")
    loader = _StubLoader({"doc.md": [chunk]})
    pipeline, _, search_client = _build_pipeline(
        loaders=[loader],
        search_results=[{"chunk_id": "KB-SAME-0001", "content_hash": chunk.content_hash}],
    )

    report = await pipeline.ingest(tmp_path)

    assert report.uploaded_chunk_ids == []
    assert report.unchanged_chunk_ids == ["KB-SAME-0001"]
    search_client.merge_or_upload_documents.assert_not_called()


async def test_ingest_uploads_a_chunk_whose_content_hash_changed(tmp_path: Path) -> None:
    (tmp_path / "doc.md").write_text("irrelevant", encoding="utf-8")
    chunk = _chunk("KB-CHANGED-0001", text="new body")
    loader = _StubLoader({"doc.md": [chunk]})
    pipeline, _, _ = _build_pipeline(
        loaders=[loader],
        search_results=[{"chunk_id": "KB-CHANGED-0001", "content_hash": "a-stale-hash"}],
        upload_results=[_FakeIndexingResult(key=chunk.chunk_id, succeeded=True)],
    )

    report = await pipeline.ingest(tmp_path)

    assert report.uploaded_chunk_ids == ["KB-CHANGED-0001"]
    assert report.unchanged_chunk_ids == []


async def test_ingest_deletes_chunks_no_longer_produced_by_any_loader(tmp_path: Path) -> None:
    (tmp_path / "doc.md").write_text("irrelevant", encoding="utf-8")
    chunk = _chunk("KB-STILL-HERE-0001")
    loader = _StubLoader({"doc.md": [chunk]})
    pipeline, _, search_client = _build_pipeline(
        loaders=[loader],
        search_results=[
            {"chunk_id": "KB-STILL-HERE-0001", "content_hash": chunk.content_hash},
            {"chunk_id": "KB-REMOVED-0002", "content_hash": "whatever"},
        ],
    )

    report = await pipeline.ingest(tmp_path)

    assert report.deleted_chunk_ids == ["KB-REMOVED-0002"]
    search_client.delete_documents.assert_called_once_with(
        documents=[{"chunk_id": "KB-REMOVED-0002"}]
    )


async def test_ingest_records_a_per_document_load_failure_without_aborting_the_run(
    tmp_path: Path,
) -> None:
    (tmp_path / "good.md").write_text("irrelevant", encoding="utf-8")
    (tmp_path / "bad.md").write_text("irrelevant", encoding="utf-8")
    good_chunk = _chunk("KB-GOOD-0001")
    from src.pipelines.knowledge_ingestion.exceptions import DocumentParseError

    loader = _StubLoader(
        {
            "good.md": [good_chunk],
            "bad.md": DocumentParseError("bad.md", "malformed"),
        }
    )
    pipeline, _, _ = _build_pipeline(
        loaders=[loader],
        search_results=[],
        upload_results=[_FakeIndexingResult(key=good_chunk.chunk_id, succeeded=True)],
    )

    report = await pipeline.ingest(tmp_path)

    assert report.uploaded_chunk_ids == ["KB-GOOD-0001"]
    assert any("bad.md" in path for path in report.failed)


async def test_ingest_records_a_per_document_upload_failure(tmp_path: Path) -> None:
    (tmp_path / "doc.md").write_text("irrelevant", encoding="utf-8")
    chunk = _chunk("KB-FAILS-0001")
    loader = _StubLoader({"doc.md": [chunk]})
    pipeline, _, _ = _build_pipeline(
        loaders=[loader],
        search_results=[],
        upload_results=[
            _FakeIndexingResult(key=chunk.chunk_id, succeeded=False, error_message="quota exceeded")
        ],
    )

    report = await pipeline.ingest(tmp_path)

    assert report.uploaded_chunk_ids == []
    assert report.failed == {"KB-FAILS-0001": "quota exceeded"}


async def test_ingest_invokes_the_embedding_provider_for_every_chunk(tmp_path: Path) -> None:
    (tmp_path / "doc.md").write_text("irrelevant", encoding="utf-8")
    chunk = _chunk("KB-EMBED-0001", text="embed me")
    loader = _StubLoader({"doc.md": [chunk]})
    embedding_provider = _RecordingEmbeddingProvider()
    pipeline, _, _ = _build_pipeline(
        loaders=[loader],
        search_results=[],
        upload_results=[_FakeIndexingResult(key=chunk.chunk_id, succeeded=True)],
        embedding_provider=embedding_provider,
    )

    await pipeline.ingest(tmp_path)

    assert embedding_provider.embedded_texts == ["embed me"]


async def test_ingest_defaults_to_the_null_embedding_provider_without_failing(
    tmp_path: Path,
) -> None:
    """No embedding_provider supplied -> KnowledgeIngestionPipeline falls back to
    NullEmbeddingProvider on its own and ingestion still completes normally — matching this
    PBI's "abstraction wired in, no real vectors" scope (see test_ingestion_embedding.py for
    NullEmbeddingProvider's own behavior, and the index schema has no vector field at all, so
    nothing here ever serializes an embedding onto the uploaded document)."""
    (tmp_path / "doc.md").write_text("irrelevant", encoding="utf-8")
    chunk = _chunk("KB-NOEMBED-0001")
    loader = _StubLoader({"doc.md": [chunk]})
    pipeline, _, search_client = _build_pipeline(
        loaders=[loader],
        search_results=[],
        upload_results=[_FakeIndexingResult(key=chunk.chunk_id, succeeded=True)],
    )

    report = await pipeline.ingest(tmp_path)

    assert report.uploaded_chunk_ids == ["KB-NOEMBED-0001"]
    _, upload_kwargs = search_client.merge_or_upload_documents.call_args
    assert "embedding" not in upload_kwargs["documents"][0]


async def test_ingest_ignores_files_no_registered_loader_matches(tmp_path: Path) -> None:
    (tmp_path / "unrelated.txt").write_text("irrelevant", encoding="utf-8")
    loader = _StubLoader({})
    pipeline, _, search_client = _build_pipeline(loaders=[loader], search_results=[])

    report = await pipeline.ingest(tmp_path)

    assert report.uploaded_chunk_ids == []
    assert report.failed == {}
    search_client.merge_or_upload_documents.assert_not_called()

"""Unit tests for the ingestion pipeline's typed contracts (PBI-03-03)."""

from src.pipelines.knowledge_ingestion.models import IngestionChunk, IngestionReport


def _chunk(text: str = "some body text", **overrides: object) -> IngestionChunk:
    defaults: dict[str, object] = {
        "chunk_id": "KB-TEST-0001",
        "source_id": "KB-TEST-0001",
        "title": "Test Document",
        "category": "test",
        "text": text,
        "source_path": "configs/knowledge_base/test.md",
    }
    defaults.update(overrides)
    return IngestionChunk(**defaults)  # type: ignore[arg-type]


def test_content_hash_is_deterministic_for_the_same_text() -> None:
    first = _chunk(text="identical content")
    second = _chunk(text="identical content")

    assert first.content_hash == second.content_hash


def test_content_hash_changes_when_text_changes() -> None:
    original = _chunk(text="original content")
    changed = _chunk(text="changed content")

    assert original.content_hash != changed.content_hash


def test_content_hash_is_present_in_serialized_output() -> None:
    """A plain @property would be silently dropped from model_dump() — content_hash must be a
    computed_field so it actually appears (see docs/sprint_02/decisions.md's
    GroundingMetadata.is_grounded precedent for the exact bug this guards against)."""
    chunk = _chunk()

    dumped = chunk.model_dump()

    assert "content_hash" in dumped
    assert dumped["content_hash"] == chunk.content_hash


def test_chunk_defaults_version_and_section_and_embedding() -> None:
    chunk = _chunk()

    assert chunk.version == "1.0.0"
    assert chunk.section is None
    assert chunk.embedding is None


def test_ingestion_report_total_processed_sums_uploaded_and_unchanged() -> None:
    report = IngestionReport(
        index_name="tmxai-knowledge-index",
        uploaded_chunk_ids=["a", "b"],
        unchanged_chunk_ids=["c"],
    )

    assert report.total_processed == 3


def test_ingestion_report_has_failures_reflects_failed_dict() -> None:
    clean = IngestionReport(index_name="tmxai-knowledge-index")
    failed = IngestionReport(index_name="tmxai-knowledge-index", failed={"a.md": "parse error"})

    assert clean.has_failures is False
    assert failed.has_failures is True

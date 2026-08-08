"""Unit tests for the Azure AI Search index schema/definition (PBI-03-03)."""

from src.pipelines.knowledge_ingestion.index_schema import (
    build_index_definition,
    chunk_to_search_document,
)
from src.pipelines.knowledge_ingestion.models import IngestionChunk


def test_build_index_definition_uses_the_supplied_index_name_not_a_literal() -> None:
    index = build_index_definition("my-configured-index-name")

    assert index.name == "my-configured-index-name"


def test_build_index_definition_declares_chunk_id_as_the_key_field() -> None:
    index = build_index_definition("tmxap-knowledge-index")

    key_fields = [field for field in index.fields if field.key]
    assert len(key_fields) == 1
    assert key_fields[0].name == "chunk_id"


def test_build_index_definition_declares_every_grounding_required_field() -> None:
    index = build_index_definition("tmxap-knowledge-index")

    field_names = {field.name for field in index.fields}
    assert field_names == {
        "chunk_id",
        "content",
        "source_id",
        "title",
        "category",
        "section",
        "source_path",
        "version",
        "content_hash",
    }


def test_chunk_to_search_document_maps_every_field_by_name() -> None:
    chunk = IngestionChunk(
        chunk_id="KB-TEST-0001",
        source_id="KB-TEST-0001",
        title="Test Document",
        category="test",
        section="Intro",
        source_path="configs/knowledge_base/test.md",
        text="the chunk body",
        version="2.0.0",
    )

    document = chunk_to_search_document(chunk)

    assert document == {
        "chunk_id": "KB-TEST-0001",
        "content": "the chunk body",
        "source_id": "KB-TEST-0001",
        "title": "Test Document",
        "category": "test",
        "section": "Intro",
        "source_path": "configs/knowledge_base/test.md",
        "version": "2.0.0",
        "content_hash": chunk.content_hash,
    }

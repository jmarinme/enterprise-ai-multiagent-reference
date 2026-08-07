"""Unit tests for the Knowledge/RAG typed contracts: valid construction, invalid-query
rejection, and the explicit has_results property for the no-results case.
"""

import pytest
from pydantic import ValidationError

from src.rag.models import KnowledgeChunk, KnowledgeMetadata, KnowledgeQuery, KnowledgeResult

_METADATA = KnowledgeMetadata(source_id="KB-TEST-0001", title="Test Doc", category="test")


def test_knowledge_query_accepts_valid_input() -> None:
    query = KnowledgeQuery(text="claim procedure", top_k=5)

    assert query.text == "claim procedure"
    assert query.top_k == 5
    assert query.category is None


def test_knowledge_query_defaults_top_k_to_three() -> None:
    query = KnowledgeQuery(text="claim procedure")

    assert query.top_k == 3


def test_knowledge_query_rejects_empty_text() -> None:
    with pytest.raises(ValidationError):
        KnowledgeQuery(text="")


def test_knowledge_query_rejects_non_positive_top_k() -> None:
    with pytest.raises(ValidationError):
        KnowledgeQuery(text="claim procedure", top_k=0)


def test_knowledge_query_rejects_top_k_above_the_bound() -> None:
    with pytest.raises(ValidationError):
        KnowledgeQuery(text="claim procedure", top_k=21)


def test_knowledge_result_has_results_is_false_for_no_matches() -> None:
    result = KnowledgeResult(query=KnowledgeQuery(text="unmatched"))

    assert result.chunks == []
    assert result.has_results is False


def test_knowledge_result_has_results_is_true_when_chunks_present() -> None:
    chunk = KnowledgeChunk(chunk_id="KB-TEST-0001", text="some text", metadata=_METADATA, score=0.5)
    result = KnowledgeResult(query=KnowledgeQuery(text="test"), chunks=[chunk])

    assert result.has_results is True


def test_knowledge_chunk_carries_source_metadata_for_citation() -> None:
    chunk = KnowledgeChunk(chunk_id="KB-TEST-0001", text="some text", metadata=_METADATA)

    assert chunk.metadata.source_id == "KB-TEST-0001"
    assert chunk.metadata.title == "Test Doc"
    assert chunk.metadata.category == "test"
    assert chunk.score == 0.0

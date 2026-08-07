"""Unit tests for the Grounding/Citations typed contracts: valid construction, camelCase
serialization for the API-facing models, and the GroundingMetadata.is_grounded property.
"""

from src.rag.grounding_models import (
    Citation,
    CitationReference,
    GroundedContext,
    GroundedResponse,
    GroundingMetadata,
)


def _citation(reference_id: str = "1", chunk_id: str = "KB-TEST-0001") -> Citation:
    return Citation(
        reference=CitationReference(reference_id=reference_id, chunk_id=chunk_id),
        document_id="KB-TEST-0001",
        title="Test Document",
        section="intro",
        source_path="configs/knowledge_base/test.md",
        score=0.75,
    )


def test_citation_preserves_every_required_field() -> None:
    citation = _citation()

    assert citation.reference.reference_id == "1"
    assert citation.reference.chunk_id == "KB-TEST-0001"
    assert citation.document_id == "KB-TEST-0001"
    assert citation.title == "Test Document"
    assert citation.section == "intro"
    assert citation.source_path == "configs/knowledge_base/test.md"
    assert citation.score == 0.75


def test_citation_section_and_source_path_are_optional() -> None:
    citation = Citation(
        reference=CitationReference(reference_id="1", chunk_id="KB-TEST-0001"),
        document_id="KB-TEST-0001",
        title="Test Document",
        score=0.5,
    )

    assert citation.section is None
    assert citation.source_path is None


def test_citation_serializes_with_camel_case_field_names() -> None:
    citation = _citation()

    dumped = citation.model_dump(by_alias=True)

    assert "documentId" in dumped
    assert "sourcePath" in dumped
    assert dumped["reference"]["referenceId"] == "1"


def test_grounding_metadata_is_grounded_reflects_citation_count() -> None:
    grounded = GroundingMetadata(retrieved_count=3, citation_count=2, top_k=2)
    ungrounded = GroundingMetadata(retrieved_count=0, citation_count=0, top_k=2)

    assert grounded.is_grounded is True
    assert ungrounded.is_grounded is False


def test_grounded_context_carries_context_text_and_citations() -> None:
    citation = _citation()
    context = GroundedContext(
        context_text="[1] some text",
        citations=[citation],
        metadata=GroundingMetadata(retrieved_count=1, citation_count=1, top_k=2),
    )

    assert context.context_text == "[1] some text"
    assert context.citations == [citation]
    assert context.metadata.is_grounded is True


def test_grounded_response_carries_text_and_citations() -> None:
    citation = _citation()
    response = GroundedResponse(text="final answer", citations=[citation])

    assert response.text == "final answer"
    assert response.citations == [citation]


def test_grounded_response_defaults_to_no_citations() -> None:
    response = GroundedResponse(text="final answer")

    assert response.citations == []

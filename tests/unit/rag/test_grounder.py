"""Unit tests for the Grounder (PBI-02-03): citation generation, duplicate removal, deterministic
ordering, metadata preservation, top-k capping, empty retrieval, and response citation
attachment.
"""

from src.rag.grounder import Grounder
from src.rag.models import KnowledgeChunk, KnowledgeMetadata


def _chunk(
    chunk_id: str,
    score: float,
    source_id: str | None = None,
    title: str = "Claims FAQ",
    category: str = "claims_procedures",
    section: str | None = "intro",
    source_path: str | None = "configs/knowledge_base/claims_faq.md",
    text: str = "sample chunk text",
) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id=chunk_id,
        text=text,
        metadata=KnowledgeMetadata(
            source_id=source_id or chunk_id,
            title=title,
            category=category,
            section=section,
            source_path=source_path,
        ),
        score=score,
    )


def test_ground_generates_one_citation_per_chunk() -> None:
    chunks = [_chunk("KB-1", 0.9), _chunk("KB-2", 0.5)]

    grounded = Grounder().ground(chunks, top_k=5)

    assert len(grounded.citations) == 2
    assert {citation.reference.chunk_id for citation in grounded.citations} == {"KB-1", "KB-2"}


def test_ground_removes_duplicate_chunk_ids_keeping_first_occurrence() -> None:
    first = _chunk("KB-1", 0.9, title="First Title")
    duplicate = _chunk("KB-1", 0.1, title="Second Title")

    grounded = Grounder().ground([first, duplicate], top_k=5)

    assert len(grounded.citations) == 1
    assert grounded.citations[0].title == "First Title"
    assert grounded.metadata.retrieved_count == 2
    assert grounded.metadata.citation_count == 1


def test_ground_orders_by_score_descending() -> None:
    low = _chunk("KB-LOW", 0.2)
    high = _chunk("KB-HIGH", 0.8)

    grounded = Grounder().ground([low, high], top_k=5)

    assert [citation.reference.chunk_id for citation in grounded.citations] == ["KB-HIGH", "KB-LOW"]


def test_ground_breaks_score_ties_by_chunk_id_ascending() -> None:
    b = _chunk("KB-B", 0.5)
    a = _chunk("KB-A", 0.5)

    grounded = Grounder().ground([b, a], top_k=5)

    assert [citation.reference.chunk_id for citation in grounded.citations] == ["KB-A", "KB-B"]


def test_ground_assigns_deterministic_sequential_reference_ids() -> None:
    chunks = [_chunk("KB-1", 0.9), _chunk("KB-2", 0.5), _chunk("KB-3", 0.1)]

    grounded = Grounder().ground(chunks, top_k=5)

    assert [citation.reference.reference_id for citation in grounded.citations] == ["1", "2", "3"]


def test_ground_caps_citations_at_top_k() -> None:
    chunks = [_chunk(f"KB-{i}", score=float(i)) for i in range(5)]

    grounded = Grounder().ground(chunks, top_k=2)

    assert len(grounded.citations) == 2
    assert grounded.metadata.retrieved_count == 5
    assert grounded.metadata.citation_count == 2
    assert grounded.metadata.top_k == 2


def test_ground_preserves_document_id_section_score_title_and_source_path() -> None:
    chunk = _chunk(
        "KB-1",
        score=0.42,
        source_id="KB-CLAIMS-0007",
        title="Claims Procedures",
        section="after-hours",
        source_path="configs/knowledge_base/claims.md",
    )

    grounded = Grounder().ground([chunk], top_k=5)

    citation = grounded.citations[0]
    assert citation.document_id == "KB-CLAIMS-0007"
    assert citation.title == "Claims Procedures"
    assert citation.section == "after-hours"
    assert citation.source_path == "configs/knowledge_base/claims.md"
    assert citation.score == 0.42


def test_ground_with_empty_chunks_returns_empty_grounded_context() -> None:
    grounded = Grounder().ground([], top_k=3)

    assert grounded.citations == []
    assert grounded.context_text == ""
    assert grounded.metadata.retrieved_count == 0
    assert grounded.metadata.citation_count == 0
    assert grounded.metadata.is_grounded is False


def test_ground_context_text_numbers_passages_matching_reference_ids() -> None:
    chunks = [_chunk("KB-1", 0.9, text="first passage"), _chunk("KB-2", 0.5, text="second passage")]

    grounded = Grounder().ground(chunks, top_k=5)

    assert grounded.context_text == "[1] first passage\n[2] second passage"


def test_build_response_attaches_exactly_the_grounded_context_citations() -> None:
    chunks = [_chunk("KB-1", 0.9), _chunk("KB-2", 0.5)]
    grounder = Grounder()
    grounded_context = grounder.ground(chunks, top_k=5)

    response = grounder.build_response("final answer text", grounded_context)

    assert response.text == "final answer text"
    assert response.citations == grounded_context.citations


def test_build_response_with_no_citations_available() -> None:
    grounder = Grounder()
    grounded_context = grounder.ground([], top_k=3)

    response = grounder.build_response("no sources found", grounded_context)

    assert response.text == "no sources found"
    assert response.citations == []

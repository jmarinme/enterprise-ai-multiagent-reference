"""Unit tests for LocalKnowledgeProvider: document loading, top-k retrieval, deterministic
ranking, the explicit no-results case, metadata/source information, category filtering, and
malformed-document handling. Runs against both isolated fixture documents (tmp_path) and the
real shipped configs/knowledge_base/ documents.
"""

from pathlib import Path

import pytest

from src.rag.exceptions import KnowledgeProviderError
from src.rag.local_provider import LocalKnowledgeProvider
from src.rag.models import KnowledgeQuery

_REAL_KNOWLEDGE_BASE = Path("configs/knowledge_base")


def _write_doc(
    directory: Path, filename: str, source_id: str, title: str, category: str, body: str
) -> None:
    content = (
        "---\n"
        f'source_id: "{source_id}"\n'
        f'title: "{title}"\n'
        f'category: "{category}"\n'
        "---\n"
        f"{body}\n"
    )
    (directory / filename).write_text(content, encoding="utf-8")


@pytest.fixture
def fixture_provider(tmp_path: Path) -> LocalKnowledgeProvider:
    _write_doc(
        tmp_path,
        "claims_doc.md",
        "KB-TEST-0001",
        "Claims Test Doc",
        "claims_procedures",
        "This document explains the claims reporting procedure and policy number requirements.",
    )
    _write_doc(
        tmp_path,
        "claims_doc_2.md",
        "KB-TEST-0002",
        "Claims Documents Test Doc",
        "claims_procedures",
        "This document explains what documents an adjuster may request after a claim.",
    )
    _write_doc(
        tmp_path,
        "broker_doc.md",
        "KB-TEST-0003",
        "Broker Test Doc",
        "broker_faq",
        "This document explains commission cycles for brokers.",
    )
    return LocalKnowledgeProvider(documents_root=tmp_path)


async def test_provider_loads_every_document_in_the_directory(fixture_provider: LocalKnowledgeProvider) -> None:
    result = await fixture_provider.retrieve(KnowledgeQuery(text="claims documents procedure", top_k=10))

    source_ids = {chunk.metadata.source_id for chunk in result.chunks}
    assert "KB-TEST-0001" in source_ids
    assert "KB-TEST-0002" in source_ids


async def test_top_k_caps_the_number_of_returned_chunks(fixture_provider: LocalKnowledgeProvider) -> None:
    result = await fixture_provider.retrieve(KnowledgeQuery(text="claims documents procedure", top_k=1))

    assert len(result.chunks) == 1


async def test_ranking_orders_the_strongest_keyword_match_first(fixture_provider: LocalKnowledgeProvider) -> None:
    result = await fixture_provider.retrieve(KnowledgeQuery(text="claims documents adjuster", top_k=10))

    assert result.chunks[0].metadata.source_id == "KB-TEST-0002"
    assert result.chunks[0].score >= result.chunks[-1].score


async def test_no_results_for_a_query_with_no_keyword_overlap(fixture_provider: LocalKnowledgeProvider) -> None:
    result = await fixture_provider.retrieve(KnowledgeQuery(text="zebra trombone lighthouse"))

    assert result.chunks == []
    assert result.has_results is False


async def test_chunks_carry_source_and_metadata_for_future_citations(
    fixture_provider: LocalKnowledgeProvider,
) -> None:
    result = await fixture_provider.retrieve(KnowledgeQuery(text="claims procedure policy"))

    chunk = result.chunks[0]
    assert chunk.metadata.source_id
    assert chunk.metadata.title
    assert chunk.metadata.category == "claims_procedures"
    assert chunk.chunk_id == chunk.metadata.source_id


async def test_category_filter_excludes_non_matching_documents(
    fixture_provider: LocalKnowledgeProvider,
) -> None:
    result = await fixture_provider.retrieve(
        KnowledgeQuery(text="claims documents commission cycles", category="broker_faq")
    )

    assert all(chunk.metadata.category == "broker_faq" for chunk in result.chunks)
    assert all(chunk.metadata.source_id == "KB-TEST-0003" for chunk in result.chunks)


async def test_retrieval_is_deterministic_across_repeated_calls(
    fixture_provider: LocalKnowledgeProvider,
) -> None:
    first = await fixture_provider.retrieve(KnowledgeQuery(text="claims documents procedure"))
    second = await fixture_provider.retrieve(KnowledgeQuery(text="claims documents procedure"))

    assert first == second


def test_raises_for_a_nonexistent_documents_root(tmp_path: Path) -> None:
    with pytest.raises(KnowledgeProviderError):
        LocalKnowledgeProvider(documents_root=tmp_path / "does-not-exist")


def test_raises_for_a_document_missing_the_frontmatter_delimiter(tmp_path: Path) -> None:
    (tmp_path / "bad.md").write_text("no frontmatter here", encoding="utf-8")

    with pytest.raises(KnowledgeProviderError):
        LocalKnowledgeProvider(documents_root=tmp_path)


def test_raises_for_a_document_with_unterminated_frontmatter(tmp_path: Path) -> None:
    (tmp_path / "bad.md").write_text('---\nsource_id: "KB-X"\n', encoding="utf-8")

    with pytest.raises(KnowledgeProviderError):
        LocalKnowledgeProvider(documents_root=tmp_path)


def test_raises_for_a_document_missing_required_frontmatter_fields(tmp_path: Path) -> None:
    (tmp_path / "bad.md").write_text('---\nsource_id: "KB-X"\n---\nbody\n', encoding="utf-8")

    with pytest.raises(KnowledgeProviderError):
        LocalKnowledgeProvider(documents_root=tmp_path)


async def test_real_shipped_knowledge_base_loads_successfully() -> None:
    provider = LocalKnowledgeProvider(documents_root=_REAL_KNOWLEDGE_BASE)

    result = await provider.retrieve(
        KnowledgeQuery(text="synthetic claim policy commission business reference platform", top_k=20)
    )

    source_ids = {chunk.metadata.source_id for chunk in result.chunks}
    assert len(source_ids) >= 5

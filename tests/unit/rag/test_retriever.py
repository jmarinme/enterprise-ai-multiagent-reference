"""Unit tests for KnowledgeRetriever: delegates to the injected provider, propagates typed
KnowledgeError as-is, and normalizes any unexpected provider failure into a typed
KnowledgeProviderError rather than letting a raw exception escape.
"""

import pytest

from src.rag.exceptions import KnowledgeProviderError
from src.rag.models import KnowledgeChunk, KnowledgeMetadata, KnowledgeQuery, KnowledgeResult
from src.rag.retriever import KnowledgeRetriever


class _StubProvider:
    def __init__(self, result: KnowledgeResult) -> None:
        self._result = result

    async def retrieve(self, query: KnowledgeQuery) -> KnowledgeResult:
        return self._result


class _RaisingTypedProvider:
    async def retrieve(self, query: KnowledgeQuery) -> KnowledgeResult:
        raise KnowledgeProviderError("stub", "simulated typed failure")


class _RaisingUnexpectedProvider:
    async def retrieve(self, query: KnowledgeQuery) -> KnowledgeResult:
        raise RuntimeError("simulated unexpected failure")


async def test_retriever_delegates_to_the_injected_provider() -> None:
    query = KnowledgeQuery(text="claim procedure")
    metadata = KnowledgeMetadata(source_id="KB-TEST-0001", title="Test", category="test")
    chunk = KnowledgeChunk(chunk_id="KB-TEST-0001", text="some text", metadata=metadata, score=1.0)
    expected = KnowledgeResult(query=query, chunks=[chunk])
    retriever = KnowledgeRetriever(provider=_StubProvider(expected))

    result = await retriever.retrieve(query)

    assert result == expected


async def test_retriever_propagates_typed_knowledge_errors_unchanged() -> None:
    retriever = KnowledgeRetriever(provider=_RaisingTypedProvider())

    with pytest.raises(KnowledgeProviderError, match="simulated typed failure"):
        await retriever.retrieve(KnowledgeQuery(text="claim procedure"))


async def test_retriever_normalizes_unexpected_provider_failures() -> None:
    retriever = KnowledgeRetriever(provider=_RaisingUnexpectedProvider())

    with pytest.raises(KnowledgeProviderError, match="simulated unexpected failure"):
        await retriever.retrieve(KnowledgeQuery(text="claim procedure"))

"""Unit tests for the embedding pipeline abstraction (PBI-03-03)."""

from src.pipelines.knowledge_ingestion.embedding import NullEmbeddingProvider


async def test_null_embedding_provider_always_returns_none() -> None:
    provider = NullEmbeddingProvider()

    result = await provider.embed("any text at all")

    assert result is None

"""KnowledgeProvider Protocol — the only interface KnowledgeRetriever depends on.

Agents depend only on KnowledgeRetriever (retriever.py) and this Protocol — never on a
concrete provider or the search technology behind it. Adding Azure AI Search in a future PBI
means adding a new class implementing this Protocol and changing the composition root
(apps/api/src/api/dependencies.py) — no change to KnowledgeRetriever or any Agent.
"""

from __future__ import annotations

from typing import Protocol

from src.rag.models import KnowledgeQuery, KnowledgeResult


class KnowledgeProvider(Protocol):
    """Contract for retrieving knowledge chunks relevant to a query."""

    async def retrieve(self, query: KnowledgeQuery) -> KnowledgeResult: ...

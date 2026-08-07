"""KnowledgeRetriever: the single entry point Agents use to retrieve knowledge context. Hides
the KnowledgeProvider and every storage/search-technology detail behind it — Agents never know
whether retrieval is local keyword scoring (this PBI) or, in a future PBI, Azure AI Search.

Mirrors PromptManager's shape (PBI-01-03): a thin wrapper that normalizes any unexpected
provider failure into a typed exception rather than letting a raw, provider-specific error
escape this boundary. Unlike ToolExecutor, this does not return an always-succeeds result —
Knowledge retrieval is a simpler, fully first-party-controlled component (locally) for which a
typed exception is more idiomatic, same reasoning as PromptManager's own decision (see
docs/sprint_01/decisions.md, PBI-01-03).
"""

from __future__ import annotations

from src.rag.exceptions import KnowledgeError, KnowledgeProviderError
from src.rag.models import KnowledgeQuery, KnowledgeResult
from src.rag.provider import KnowledgeProvider


class KnowledgeRetriever:
    """The single entry point Agents use to retrieve knowledge context."""

    def __init__(self, provider: KnowledgeProvider) -> None:
        self._provider = provider

    async def retrieve(self, query: KnowledgeQuery) -> KnowledgeResult:
        try:
            return await self._provider.retrieve(query)
        except KnowledgeError:
            raise
        except Exception as exc:
            # Normalize any unexpected provider failure into a typed exception rather than
            # letting a raw, provider-specific error escape this boundary — mirrors
            # PromptManager._load()'s identical normalization (PBI-01-03).
            raise KnowledgeProviderError("unknown", str(exc)) from exc

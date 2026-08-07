"""Typed exceptions for the Knowledge/RAG retrieval framework."""

from __future__ import annotations


class KnowledgeError(Exception):
    """Base class for all Knowledge/RAG framework errors."""


class KnowledgeProviderError(KnowledgeError):
    """Raised when the underlying provider fails for a reason not covered by a more specific
    typed exception — e.g. a misconfigured documents root, or (for a future provider) a
    downstream search-service failure."""

    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        self.message = message
        super().__init__(f"Knowledge provider '{provider}' failed: {message}")

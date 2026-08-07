"""Typed exceptions for the Knowledge/RAG retrieval framework."""

from __future__ import annotations


class KnowledgeError(Exception):
    """Base class for all Knowledge/RAG framework errors."""


class KnowledgeConfigurationError(KnowledgeError):
    """Raised when required KnowledgeProvider configuration (endpoint, index name,
    credentials) is missing or invalid — mirrors LLMConfigurationError."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class KnowledgeProviderError(KnowledgeError):
    """Raised when the underlying provider fails for a reason not covered by a more specific
    typed exception — e.g. a misconfigured documents root, or a downstream search-service
    failure (authentication, generic HTTP error)."""

    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        self.message = message
        super().__init__(f"Knowledge provider '{provider}' failed: {message}")


class KnowledgeTimeoutError(KnowledgeProviderError):
    """Raised when the provider call exceeds its configured timeout or fails at the transport
    level (connection refused, DNS failure, etc.) — mirrors LLMTimeoutError."""

    def __init__(self, provider: str, message: str = "request timed out") -> None:
        super().__init__(provider, message)

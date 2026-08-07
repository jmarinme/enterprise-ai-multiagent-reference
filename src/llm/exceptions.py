"""Typed exceptions for the LLM Adapter framework."""

from __future__ import annotations


class LLMError(Exception):
    """Base class for all LLM framework errors."""


class LLMConfigurationError(LLMError):
    """Raised when required LLM configuration (endpoint, deployment, credentials) is missing
    or invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class LLMProviderError(LLMError):
    """Raised when the underlying provider fails for a reason not covered by a more specific
    typed exception below."""

    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        self.message = message
        super().__init__(f"LLM provider '{provider}' failed: {message}")


class LLMRateLimitError(LLMProviderError):
    """Raised when the provider reports the request was rate-limited/throttled."""

    def __init__(self, provider: str, message: str = "rate limited") -> None:
        super().__init__(provider, message)


class LLMTimeoutError(LLMProviderError):
    """Raised when the provider call exceeds its configured timeout."""

    def __init__(self, provider: str, message: str = "request timed out") -> None:
        super().__init__(provider, message)


class LLMContentSafetyError(LLMProviderError):
    """Raised when the provider blocks a request/response for content-safety reasons."""

    def __init__(self, provider: str, message: str = "blocked by content safety") -> None:
        super().__init__(provider, message)

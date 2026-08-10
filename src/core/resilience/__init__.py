"""Resilience primitives (CLAUDE.md architecture principle #9: "timeouts, retries with backoff,
idempotency, and circuit breakers where applicable") — resolves Architecture Review Finding A-07.

Two small, provider-agnostic building blocks: `retry_with_backoff` (exponential backoff + full
jitter, retrying only the exception types the caller names as transient) and `CircuitBreaker`
(per-process, in-memory — matches this platform's existing `@lru_cache` per-process singleton
scope, see Finding A-06). Neither is imported by Agents/Supervisor — only by the three provider
adapters that make real external calls (Azure OpenAI, Cosmos DB, Azure AI Search).
"""

from __future__ import annotations

from src.core.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
)
from src.core.resilience.retry import retry_with_backoff

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "CircuitState",
    "retry_with_backoff",
]

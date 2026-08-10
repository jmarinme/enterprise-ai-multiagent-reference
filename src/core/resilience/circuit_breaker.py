"""Lightweight, per-process, in-memory circuit breaker.

Not distributed/shared across Container App replicas — an intentional, documented scope
boundary matching this platform's existing per-process `@lru_cache` singleton pattern
(apps/api/src/api/dependencies.py, Architecture Review Finding A-06). Each provider adapter
(Azure OpenAI, Cosmos, Azure AI Search) owns exactly one `CircuitBreaker` instance for its own
process lifetime, constructed once in `__init__`.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from enum import Enum
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(Exception):
    """Raised when a call is rejected because the circuit is open — the downstream dependency
    has failed repeatedly and is being given time to recover; this call was never attempted."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(
            f"Circuit breaker '{name}' is open — failing fast without calling downstream"
        )


class CircuitBreaker:
    """Three states: CLOSED (normal — failures counted), OPEN (fail fast, no call attempted),
    HALF_OPEN (one trial call allowed once `reset_timeout_seconds` has elapsed since opening —
    success closes the circuit, failure reopens it immediately regardless of the failure
    threshold)."""

    def __init__(
        self,
        name: str,
        *,
        failure_threshold: int = 5,
        reset_timeout_seconds: float = 30.0,
    ) -> None:
        self._name = name
        self._failure_threshold = failure_threshold
        self._reset_timeout_seconds = reset_timeout_seconds
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> CircuitState:
        """CLOSED/OPEN are stored; HALF_OPEN is derived — true once `_opened_at` is old enough,
        without needing a separate timer/background task."""
        if (
            self._state == CircuitState.OPEN
            and self._opened_at is not None
            and time.monotonic() - self._opened_at >= self._reset_timeout_seconds
        ):
            return CircuitState.HALF_OPEN
        return self._state

    async def call(self, operation: Callable[[], Awaitable[T]]) -> T:
        """Runs `operation()` if the circuit allows it; raises `CircuitBreakerOpenError`
        immediately (without calling `operation`) if it does not."""
        current_state = self.state
        if current_state == CircuitState.OPEN:
            raise CircuitBreakerOpenError(self._name)

        is_trial = current_state == CircuitState.HALF_OPEN
        try:
            result = await operation()
        except Exception:
            self._on_failure(is_trial=is_trial)
            raise
        else:
            self._on_success()
            return result

    def _on_success(self) -> None:
        if self._state != CircuitState.CLOSED:
            logger.info("Circuit breaker '%s' closing after a successful call", self._name)
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at = None

    def _on_failure(self, *, is_trial: bool) -> None:
        self._failure_count += 1
        # A half-open trial call failing reopens the circuit immediately, regardless of the
        # accumulated failure count — the whole point of the trial was to check recovery, and
        # it didn't recover.
        if is_trial or self._failure_count >= self._failure_threshold:
            if self._state != CircuitState.OPEN:
                logger.warning(
                    "Circuit breaker '%s' opening after %d failure(s)",
                    self._name,
                    self._failure_count,
                )
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()

"""Generic async retry-with-exponential-backoff helper.

Retries only the exception types the caller explicitly names as transient
(`retryable_exceptions`) — any other exception propagates on the first attempt, unretried. This
is how "do not retry non-transient business errors" is enforced: by the caller's own
classification, never by guessing here. `is_retryable` optionally narrows further (e.g. a Cosmos
409/404 status code inside an otherwise-retryable exception type).
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def retry_with_backoff(  # noqa: UP047 -- PEP 695 `async def f[T](...)` is not parsed by mypy 1.20.2 (confirmed: "error: Expected '('"); TypeVar is the mypy-compatible form, and CLAUDE.md requires mypy-clean code.
    operation: Callable[[], Awaitable[T]],
    *,
    retryable_exceptions: tuple[type[Exception], ...],
    max_attempts: int = 3,
    base_delay_seconds: float = 0.5,
    max_delay_seconds: float = 8.0,
    operation_name: str = "operation",
    is_retryable: Callable[[Exception], bool] | None = None,
) -> T:
    """Calls `operation()` up to `max_attempts` times, retrying only on `retryable_exceptions`
    (optionally narrowed by `is_retryable`), with exponential backoff and full jitter
    (`random.uniform(0, delay)` — avoids a thundering herd of synchronized retries).

    Raises the last exception once `max_attempts` is reached, or immediately (no retry) for any
    exception not in `retryable_exceptions`, or for which `is_retryable` returns False.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            return await operation()
        except retryable_exceptions as exc:
            if is_retryable is not None and not is_retryable(exc):
                raise
            if attempt >= max_attempts:
                logger.warning(
                    "%s failed after %d attempt(s), giving up: %s",
                    operation_name,
                    attempt,
                    exc,
                )
                raise
            delay = min(max_delay_seconds, base_delay_seconds * (2 ** (attempt - 1)))
            delay = random.uniform(0, delay)
            logger.warning(
                "%s failed on attempt %d/%d (%s), retrying in %.2fs",
                operation_name,
                attempt,
                max_attempts,
                exc,
                delay,
            )
            await asyncio.sleep(delay)

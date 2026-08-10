"""Tests for src.core.resilience.retry.retry_with_backoff (Architecture Review Finding A-07)."""

from __future__ import annotations

import pytest

from src.core.resilience.retry import retry_with_backoff


class _TransientError(Exception):
    pass


class _BusinessError(Exception):
    pass


async def test_succeeds_on_first_attempt_without_sleeping() -> None:
    calls = 0

    async def operation() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    result = await retry_with_backoff(
        operation, retryable_exceptions=(_TransientError,), base_delay_seconds=0.001
    )

    assert result == "ok"
    assert calls == 1


async def test_retries_transient_failures_then_succeeds() -> None:
    calls = 0

    async def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise _TransientError("temporary")
        return "recovered"

    result = await retry_with_backoff(
        operation,
        retryable_exceptions=(_TransientError,),
        max_attempts=5,
        base_delay_seconds=0.001,
        max_delay_seconds=0.002,
    )

    assert result == "recovered"
    assert calls == 3


async def test_gives_up_after_max_attempts() -> None:
    calls = 0

    async def operation() -> str:
        nonlocal calls
        calls += 1
        raise _TransientError("still failing")

    with pytest.raises(_TransientError):
        await retry_with_backoff(
            operation,
            retryable_exceptions=(_TransientError,),
            max_attempts=3,
            base_delay_seconds=0.001,
            max_delay_seconds=0.002,
        )

    assert calls == 3


async def test_never_retries_a_non_transient_exception() -> None:
    """The core 'do not retry non-transient business errors' guarantee: an exception type not
    listed in retryable_exceptions propagates on the very first attempt."""
    calls = 0

    async def operation() -> str:
        nonlocal calls
        calls += 1
        raise _BusinessError("invalid request, retrying would never help")

    with pytest.raises(_BusinessError):
        await retry_with_backoff(
            operation,
            retryable_exceptions=(_TransientError,),
            max_attempts=5,
            base_delay_seconds=0.001,
        )

    assert calls == 1


async def test_is_retryable_predicate_can_narrow_a_retryable_exception_type() -> None:
    """A predicate can veto retrying even a listed exception type — e.g. distinguishing a
    Cosmos 429 (retry) from a 404 raised via the same exception class (never retry)."""
    calls = 0

    class _HttpError(Exception):
        def __init__(self, status_code: int) -> None:
            self.status_code = status_code
            super().__init__(f"http {status_code}")

    async def operation() -> str:
        nonlocal calls
        calls += 1
        raise _HttpError(404)

    with pytest.raises(_HttpError):
        await retry_with_backoff(
            operation,
            retryable_exceptions=(_HttpError,),
            max_attempts=5,
            base_delay_seconds=0.001,
            is_retryable=lambda exc: getattr(exc, "status_code", None) in {408, 429, 500, 503},
        )

    assert calls == 1

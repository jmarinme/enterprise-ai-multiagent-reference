"""Tests for src.core.resilience.circuit_breaker.CircuitBreaker (Architecture Review Finding A-07)."""

from __future__ import annotations

import pytest

from src.core.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
)


class _DownstreamError(Exception):
    pass


async def test_starts_closed_and_stays_closed_on_success() -> None:
    breaker = CircuitBreaker("test", failure_threshold=3, reset_timeout_seconds=30.0)

    async def ok() -> str:
        return "ok"

    assert breaker.state == CircuitState.CLOSED
    result = await breaker.call(ok)
    assert result == "ok"
    assert breaker.state == CircuitState.CLOSED


async def test_opens_after_reaching_the_failure_threshold() -> None:
    breaker = CircuitBreaker("test", failure_threshold=3, reset_timeout_seconds=30.0)

    async def failing() -> str:
        raise _DownstreamError("down")

    for _ in range(3):
        with pytest.raises(_DownstreamError):
            await breaker.call(failing)

    assert breaker.state == CircuitState.OPEN


async def test_open_circuit_fails_fast_without_calling_the_operation() -> None:
    breaker = CircuitBreaker("test", failure_threshold=1, reset_timeout_seconds=30.0)
    calls = 0

    async def failing() -> str:
        nonlocal calls
        calls += 1
        raise _DownstreamError("down")

    with pytest.raises(_DownstreamError):
        await breaker.call(failing)
    assert breaker.state == CircuitState.OPEN
    assert calls == 1

    with pytest.raises(CircuitBreakerOpenError):
        await breaker.call(failing)
    # The operation itself was never invoked the second time — fail-fast, not fail-slow.
    assert calls == 1


async def test_half_open_trial_success_closes_the_circuit() -> None:
    breaker = CircuitBreaker("test", failure_threshold=1, reset_timeout_seconds=0.0)

    async def failing() -> str:
        raise _DownstreamError("down")

    with pytest.raises(_DownstreamError):
        await breaker.call(failing)
    assert breaker.state == CircuitState.HALF_OPEN  # reset_timeout_seconds=0.0 elapses instantly

    async def recovered() -> str:
        return "back up"

    result = await breaker.call(recovered)
    assert result == "back up"
    assert breaker.state == CircuitState.CLOSED


async def test_half_open_trial_failure_reopens_immediately_regardless_of_threshold() -> None:
    """A single failed trial call reopens the circuit even with a high failure_threshold —
    the trial's whole purpose is proving recovery, and it didn't. Uses a small positive
    reset_timeout (not exactly 0.0) so the OPEN state is observable between the two calls —
    with 0.0 the circuit would already be back in its (correct) HALF_OPEN view an instant
    after opening, since zero time need elapse for the timeout to be satisfied."""
    breaker = CircuitBreaker("test", failure_threshold=1, reset_timeout_seconds=0.05)

    async def failing() -> str:
        raise _DownstreamError("down")

    with pytest.raises(_DownstreamError):
        await breaker.call(failing)
    assert breaker.state == CircuitState.OPEN

    import asyncio

    await asyncio.sleep(0.06)
    assert breaker.state == CircuitState.HALF_OPEN

    with pytest.raises(_DownstreamError):
        await breaker.call(failing)
    assert breaker.state == CircuitState.OPEN


async def test_stays_open_until_reset_timeout_elapses() -> None:
    breaker = CircuitBreaker("test", failure_threshold=1, reset_timeout_seconds=999.0)

    async def failing() -> str:
        raise _DownstreamError("down")

    with pytest.raises(_DownstreamError):
        await breaker.call(failing)
    assert breaker.state == CircuitState.OPEN

    with pytest.raises(CircuitBreakerOpenError):
        await breaker.call(failing)
    assert breaker.state == CircuitState.OPEN

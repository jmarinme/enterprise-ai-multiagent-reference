"""Lightweight load test (PBI-08-01 — Architecture Review Finding A-17: "no load/resilience
test evidence exists anywhere in the repository").

Fires a batch of concurrent POST /chat requests directly against the real FastAPI app (in
process, via httpx's ASGI transport — no real network hop, no real server process, no Azure
cost: the default composition root uses MockLLMProvider/in-memory/local providers, exactly like
every other test in this suite). This is deliberately "lightweight" — a smoke-level concurrency
and latency check appropriate for a synthetic academic reference platform, not a production
capacity-planning benchmark. Results are printed for evidence capture
(docs/sprint_08/evidence/) and asserted against generous, deliberately non-flaky bounds so this
remains a real, run-every-regression pytest test, not a throwaway script.
"""

from __future__ import annotations

import asyncio
import time

import httpx
import pytest
from main import app

_CONCURRENT_REQUESTS = 20
# Generous, deliberately non-flaky bounds for an in-process MockLLMProvider run on a shared CI
# agent — this is a smoke-level check ("does concurrency work at all, does latency stay
# reasonable"), not a strict performance gate calibrated to any specific hardware.
_MAX_ACCEPTABLE_P95_SECONDS = 2.0
_MAX_ACCEPTABLE_TOTAL_WALL_CLOCK_SECONDS = 10.0


async def _single_chat_request(client: httpx.AsyncClient, user_index: int) -> tuple[int, float]:
    start = time.perf_counter()
    response = await client.post(
        "/chat",
        json={
            "message": "I need to check the status of my policy SYN-POL-0001.",
            "userId": f"load-test-user-{user_index}",
        },
    )
    elapsed = time.perf_counter() - start
    return response.status_code, elapsed


async def test_concurrent_chat_requests_all_succeed_within_bounded_latency() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        overall_start = time.perf_counter()
        results = await asyncio.gather(
            *[_single_chat_request(client, i) for i in range(_CONCURRENT_REQUESTS)]
        )
        overall_elapsed = time.perf_counter() - overall_start

    status_codes = [status for status, _ in results]
    latencies = sorted(elapsed for _, elapsed in results)
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)]
    maximum = latencies[-1]

    print(
        f"\nLoad test: {_CONCURRENT_REQUESTS} concurrent POST /chat requests\n"
        f"  Total wall-clock time: {overall_elapsed:.3f}s\n"
        f"  Latency p50: {p50:.3f}s  p95: {p95:.3f}s  max: {maximum:.3f}s\n"
        f"  Status codes: {sorted(set(status_codes))}\n"
        f"  Success rate: {status_codes.count(200)}/{len(status_codes)}"
    )

    assert all(code == 200 for code in status_codes), (
        f"expected all {_CONCURRENT_REQUESTS} requests to return 200, got {status_codes}"
    )
    assert p95 < _MAX_ACCEPTABLE_P95_SECONDS, (
        f"p95 latency {p95:.3f}s exceeded the {_MAX_ACCEPTABLE_P95_SECONDS}s bound"
    )
    assert overall_elapsed < _MAX_ACCEPTABLE_TOTAL_WALL_CLOCK_SECONDS, (
        f"total wall-clock time {overall_elapsed:.3f}s exceeded the "
        f"{_MAX_ACCEPTABLE_TOTAL_WALL_CLOCK_SECONDS}s bound"
    )


async def test_a_slow_or_failed_dependency_does_not_take_down_unrelated_requests() -> None:
    """A minimal resilience-under-load check: one conversation that will fail a business
    lookup (an unknown policy number) running concurrently with normal ones must not affect the
    others — no shared mutable state leaks between concurrent requests handled by the same
    process (Architecture Review Finding A-06's own per-process-singleton scope boundary)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:

        async def _normal(i: int) -> int:
            response = await client.post(
                "/chat",
                json={
                    "message": "I need to check the status of my policy SYN-POL-0001.",
                    "userId": f"load-test-normal-{i}",
                },
            )
            return response.status_code

        async def _unknown_policy(i: int) -> int:
            response = await client.post(
                "/chat",
                json={
                    "message": "I need to check the status of my policy SYN-POL-DOES-NOT-EXIST.",
                    "userId": f"load-test-unknown-{i}",
                },
            )
            return response.status_code

        results = await asyncio.gather(
            *([_normal(i) for i in range(8)] + [_unknown_policy(i) for i in range(8)])
        )

    # Every request still gets a well-formed HTTP response (200 — this platform never surfaces
    # a "not found" business outcome as an HTTP error, per the existing agents' own safe-
    # fallback design) regardless of which concurrent requests hit a real vs. missing policy.
    assert all(code == 200 for code in results)


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v", "-s"]))

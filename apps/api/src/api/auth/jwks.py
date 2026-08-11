"""Fetches and caches Microsoft Entra ID's JSON Web Key Set (JWKS) — the public signing keys
used to verify a v2.0 access token's signature.

Injectable (constructor-supplied fetcher), matching this codebase's existing provider-swap
pattern for every other external dependency (ADR-0006) — tests supply a fixed key set instead
of a live network call; production uses the real Microsoft endpoint.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

import httpx

# The multi-tenant JWKS endpoint under /common — valid for verifying v2.0 tokens issued by
# any Entra ID tenant via this platform's /common authority (PBI-11-01). There is no
# per-tenant JWKS to choose between here; Microsoft publishes one shared key set for the
# common endpoint.
DEFAULT_JWKS_URL = "https://login.microsoftonline.com/common/discovery/v2.0/keys"
_CACHE_TTL_SECONDS = 24 * 60 * 60
_FETCH_TIMEOUT_SECONDS = 10.0

JwksFetcher = Callable[[str], Awaitable[dict]]


async def _fetch_jwks(url: str) -> dict:
    async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT_SECONDS) as client:
        response = await client.get(url)
        response.raise_for_status()
        result: dict = response.json()
        return result


class JwksProvider:
    """Caches the fetched key set in-process (per-process, matching this codebase's existing
    per-process caching posture — CircuitBreaker's own docstring, Architecture Review Finding
    A-06) for up to _CACHE_TTL_SECONDS, refreshing once immediately if a requested `kid` is
    not found in the cached set (covers real key rotation without waiting a full day)."""

    def __init__(self, jwks_url: str = DEFAULT_JWKS_URL, *, fetcher: JwksFetcher | None = None) -> None:
        self._jwks_url = jwks_url
        self._fetcher = fetcher or _fetch_jwks
        self._cache: dict | None = None
        self._cached_at: float = 0.0

    async def get_keys(self, *, force_refresh: bool = False) -> dict:
        now = time.monotonic()
        if not force_refresh and self._cache is not None and (now - self._cached_at) < _CACHE_TTL_SECONDS:
            return self._cache
        self._cache = await self._fetcher(self._jwks_url)
        self._cached_at = now
        return self._cache

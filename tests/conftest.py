"""Shared test infrastructure for Entra ID authentication (PBI-11-01).

Generates one RSA keypair per test session and exposes helpers to mint real, cryptographically
valid (or deliberately invalid) JWTs against it, plus a JwksProvider that serves the matching
public key set without any network call — the same api.auth.jwks.JwksProvider class production
uses, just constructed with a test fetcher (api.auth's own provider-swap seam, ADR-0006).

Also makes apps/api/src importable, consolidating what every existing tests/**/conftest.py
already did individually.
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

_API_SRC = Path(__file__).resolve().parent.parent / "apps" / "api" / "src"
if str(_API_SRC) not in sys.path:
    sys.path.insert(0, str(_API_SRC))

from api.auth.dependency import get_current_user
from api.auth.jwks import JwksProvider
from api.auth.models import AuthenticatedUser
from fastapi import Request
from main import app

# PBI-11-01D: a real, live Entra v2.0 access token (ver=2.0) from this exact App Registration
# carries the bare API client ID GUID as `aud` — never the "api://..." Application ID URI
# (that is the frontend's requested scope/resource identifier, not this token's audience).
TEST_ENTRA_API_AUDIENCE = "67d95215-5a31-416a-99ab-5fe203fb7c32"
# The pre-PBI-11-01D (incorrect) audience value — used only to regression-test that it is now
# rejected, not accepted alongside the real one.
_LEGACY_APPLICATION_ID_URI_AUDIENCE = "api://67d95215-5a31-416a-99ab-5fe203fb7c32"
TEST_TENANT_ID = "11111111-1111-1111-1111-111111111111"
OTHER_TEST_TENANT_ID = "22222222-2222-2222-2222-222222222222"

_KEY_ID = "test-signing-key-1"
_OTHER_KEY_ID = "test-signing-key-2"

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _to_jwk(public_key: Any, kid: str) -> dict:
    jwk = json.loads(RSAAlgorithm.to_jwk(public_key))
    jwk["kid"] = kid
    jwk["use"] = "sig"
    jwk["alg"] = "RS256"
    return jwk


_TEST_JWKS = {
    "keys": [
        _to_jwk(_private_key.public_key(), _KEY_ID),
        _to_jwk(_other_private_key.public_key(), _OTHER_KEY_ID),
    ]
}


def make_fake_jwks_provider() -> JwksProvider:
    """A JwksProvider backed by this module's test key set — no network call, ever."""

    async def _fetcher(_url: str) -> dict:
        return _TEST_JWKS

    return JwksProvider(fetcher=_fetcher)


def default_claims(*, tid: str = TEST_TENANT_ID, oid: str | None = None) -> dict:
    """A realistic, currently-valid Entra ID v2.0 access-token claim set for TEST_ENTRA_API_AUDIENCE."""
    now = int(time.time())
    oid = oid or str(uuid.uuid4())
    return {
        "aud": TEST_ENTRA_API_AUDIENCE,
        "iss": f"https://login.microsoftonline.com/{tid}/v2.0",
        "iat": now,
        "nbf": now,
        "exp": now + 3600,
        "sub": str(uuid.uuid4()),
        "oid": oid,
        "tid": tid,
        "name": "Test User",
        "preferred_username": "test.user@example.com",
        "scp": "access_as_user",
    }


def mint_token(
    claims: dict | None = None,
    *,
    key: Any = None,
    kid: str = _KEY_ID,
    **claim_overrides: object,
) -> str:
    """Signs `claims` (defaulting to a valid claim set, with any overrides applied) as a real
    RS256 JWT using this module's test private key (or `key`, e.g. _other_private_key, to
    produce a token whose signature will NOT verify against the published test JWKS)."""
    payload = dict(claims if claims is not None else default_claims())
    payload.update(claim_overrides)
    signing_key = key if key is not None else _private_key
    return jwt.encode(payload, signing_key, algorithm="RS256", headers={"kid": kid})


def mint_expired_token(**claim_overrides: object) -> str:
    claims = default_claims()
    claims["iat"] = int(time.time()) - 7200
    claims["exp"] = int(time.time()) - 3600
    claims.update(claim_overrides)
    return mint_token(claims)


def mint_wrong_audience_token(**claim_overrides: object) -> str:
    """A different bare GUID than this API's real client ID — the general "wrong audience"
    shape (e.g. a token actually issued for a different application)."""
    claims = default_claims()
    claims["aud"] = "99999999-9999-9999-9999-999999999999"
    claims.update(claim_overrides)
    return mint_token(claims)


def mint_application_id_uri_audience_token(**claim_overrides: object) -> str:
    """PBI-11-01D regression: `aud` set to the "api://..." Application ID URI — the value this
    API's audience check used to (incorrectly) expect before it was corrected against a real
    live v2.0 token. This must now be rejected: a v2.0 token never carries this shape as its
    audience, so accepting it would mean accepting tokens no genuine v2.0 flow could produce."""
    claims = default_claims()
    claims["aud"] = _LEGACY_APPLICATION_ID_URI_AUDIENCE
    claims.update(claim_overrides)
    return mint_token(claims)


def mint_wrong_signature_token(**claim_overrides: object) -> str:
    """`kid` claims to be _KEY_ID (whose public key IS in the test JWKS), but the token is
    actually signed with _other_private_key — the validator resolves _KEY_ID's real public
    key, which does not match the actual signer, so signature verification must fail. This is
    the exact shape of a forged/tampered token, not merely an unknown `kid`."""
    claims = default_claims()
    claims.update(claim_overrides)
    return mint_token(claims, key=_other_private_key, kid=_KEY_ID)


def mint_malformed_issuer_token(**claim_overrides: object) -> str:
    """A structurally valid, correctly-signed token whose `iss` does not match its own `tid`
    — the exact cross-tenant-forgery shape the /common issuer check must reject."""
    claims = default_claims(tid=TEST_TENANT_ID)
    claims["iss"] = f"https://login.microsoftonline.com/{OTHER_TEST_TENANT_ID}/v2.0"
    claims.update(claim_overrides)
    return mint_token(claims)


@pytest.fixture
def fake_jwks_provider() -> JwksProvider:
    return make_fake_jwks_provider()


async def _identity_from_deprecated_userid(request: Request) -> AuthenticatedUser:
    """Test-only convenience override for get_current_user (PBI-11-01): derives a stable test
    identity from whatever the (now-deprecated) `userId` field/query param the request already
    carries, preserving every pre-existing test's per-user isolation assertions unmodified —
    real Entra ID token-validation correctness is covered exhaustively by
    tests/unit/api/test_auth.py, which opts out of this override (see below). Never used
    outside the test process; production's get_current_user always requires and validates a
    real Bearer token."""
    user_id: str | None = None
    if request.method == "GET":
        user_id = request.query_params.get("userId")
    else:
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001 -- any unparsable body just falls through to the default
            body = {}
        user_id = body.get("userId") if isinstance(body, dict) else None
    user_id = user_id or "test-default-user"
    return AuthenticatedUser(user_id=user_id, oid=user_id, tid="test-tenant", name=None, email=None)


@pytest.fixture(autouse=True)
def _auth_override(request: pytest.FixtureRequest):
    """Applies `_identity_from_deprecated_userid` as the FastAPI `get_current_user` dependency
    for every test under tests/, EXCEPT modules marked `no_auth_override`
    (tests/unit/api/test_auth.py) — see that module's own docstring for why it must exercise
    the real dependency instead."""
    if request.node.get_closest_marker("no_auth_override") is not None:
        yield
        return
    app.dependency_overrides[get_current_user] = _identity_from_deprecated_userid
    yield
    app.dependency_overrides.pop(get_current_user, None)

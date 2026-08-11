"""Entra ID authentication tests (PBI-11-01).

Two layers, deliberately kept separate:

1. Direct EntraTokenValidator tests — prove the actual cryptographic/claim validation logic
   (signature, expiry, audience, tenant-self-consistent issuer) is correct, using real RS256
   JWTs signed against a test keypair and a fake (network-free) JWKS provider.
2. Real HTTP tests through the FastAPI app (TestClient) — prove the dependency is actually
   wired onto the protected routes and returns 401 for every rejection path, plus the IDOR/
   identity-isolation regression this PBI exists to close.

This module is deliberately excluded from the "echo the deprecated userId field" convenience
auth override applied to the rest of tests/unit/api/ (see conftest.py's `no_auth_override`
marker) — every test here exercises the real get_current_user/EntraTokenValidator plumbing,
never a bypass.
"""

from __future__ import annotations

import pytest
from api.auth.dependency import get_token_validator
from api.auth.exceptions import TokenValidationError
from api.auth.validator import EntraTokenValidator
from fastapi.testclient import TestClient
from main import app

from tests.conftest import (
    TEST_ENTRA_API_AUDIENCE,
    default_claims,
    make_fake_jwks_provider,
    mint_application_id_uri_audience_token,
    mint_expired_token,
    mint_malformed_issuer_token,
    mint_token,
    mint_wrong_audience_token,
    mint_wrong_signature_token,
)

pytestmark = pytest.mark.no_auth_override

client = TestClient(app)


def _validator() -> EntraTokenValidator:
    return EntraTokenValidator(audience=TEST_ENTRA_API_AUDIENCE, jwks_provider=make_fake_jwks_provider())


# ---------------------------------------------------------------------------
# 1. EntraTokenValidator — direct, real cryptographic validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validator_accepts_a_valid_token_and_derives_tid_qualified_identity() -> None:
    """PBI-11-01D: TEST_ENTRA_API_AUDIENCE is the bare API client ID GUID, matching a real
    live Entra v2.0 token's `aud` claim exactly (ver=2.0, confirmed live) — not the
    "api://..." Application ID URI."""
    claims = default_claims()
    assert claims["aud"] == "67d95215-5a31-416a-99ab-5fe203fb7c32"
    token = mint_token(claims)

    user = await _validator().validate(token)

    assert user.oid == claims["oid"]
    assert user.tid == claims["tid"]
    assert user.user_id == f"{claims['tid']}:{claims['oid']}"
    # Display fields only — never part of the authorization identity.
    assert user.name == "Test User"
    assert user.email == "test.user@example.com"


@pytest.mark.asyncio
async def test_validator_accepts_a_token_with_the_access_as_user_scope_claim() -> None:
    """PBI-11-01D: the token's `scp` claim (granted delegated scope) remains
    "access_as_user" end to end — this API does not itself gate on scope content beyond
    requiring a validly-signed, correctly-audienced token, so this proves the claim survives
    validation unmodified rather than being stripped or rejected."""
    claims = default_claims()
    assert claims["scp"] == "access_as_user"
    token = mint_token(claims)

    user = await _validator().validate(token)

    assert user.oid == claims["oid"]


@pytest.mark.asyncio
async def test_validator_rejects_an_expired_token() -> None:
    token = mint_expired_token()

    with pytest.raises(TokenValidationError):
        await _validator().validate(token)


@pytest.mark.asyncio
async def test_validator_rejects_a_wrong_audience_token() -> None:
    """A token issued for a different application entirely (a different bare GUID)."""
    token = mint_wrong_audience_token()

    with pytest.raises(TokenValidationError):
        await _validator().validate(token)


@pytest.mark.asyncio
async def test_validator_rejects_the_legacy_application_id_uri_as_audience() -> None:
    """PBI-11-01D core regression: this API's audience check previously (incorrectly)
    expected "api://67d95215-.../access_as_user" as `aud`. A real v2.0 token never carries
    that shape as its audience (confirmed live), so a token claiming it must now be rejected
    — proving the fix actually narrowed acceptance rather than adding a second accepted
    value alongside the correct one."""
    token = mint_application_id_uri_audience_token()

    with pytest.raises(TokenValidationError):
        await _validator().validate(token)


@pytest.mark.asyncio
async def test_validator_rejects_a_forged_signature_even_with_a_known_kid() -> None:
    """A token whose `kid` names a real published key, but whose signature was actually
    produced by a different key — the exact shape of a tampered/forged token."""
    token = mint_wrong_signature_token()

    with pytest.raises(TokenValidationError):
        await _validator().validate(token)


@pytest.mark.asyncio
async def test_validator_rejects_a_token_signed_by_a_completely_unknown_key() -> None:
    """No JWK in the (test) JWKS matches this token's kid at all."""
    token = mint_token(default_claims(), kid="never-published-key-id")

    with pytest.raises(TokenValidationError):
        await _validator().validate(token)


@pytest.mark.asyncio
async def test_validator_rejects_a_malformed_multitenant_issuer() -> None:
    """A correctly-signed token whose `iss` does not match its own `tid` (a cross-tenant
    mismatch) — proves the /common issuer check is real, not disabled/weakened."""
    token = mint_malformed_issuer_token()

    with pytest.raises(TokenValidationError):
        await _validator().validate(token)


@pytest.mark.asyncio
async def test_validator_accepts_tokens_from_different_tenants_under_common() -> None:
    """The whole point of /common: a token from ANY tenant is accepted, as long as its issuer
    is self-consistent with its own tid — this is not a fixed single-tenant allowlist."""
    tenant_a_token = mint_token(default_claims(tid="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
    tenant_b_token = mint_token(default_claims(tid="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"))

    user_a = await _validator().validate(tenant_a_token)
    user_b = await _validator().validate(tenant_b_token)

    assert user_a.tid == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert user_b.tid == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    assert user_a.user_id != user_b.user_id


@pytest.mark.asyncio
async def test_validator_rejects_a_token_missing_oid_claim() -> None:
    claims = default_claims()
    del claims["oid"]
    token = mint_token(claims)

    with pytest.raises(TokenValidationError):
        await _validator().validate(token)


@pytest.mark.asyncio
async def test_validator_rejects_an_unsigned_none_algorithm_token() -> None:
    """PyJWT refuses to decode an alg="none" token against an RSA key by construction, but
    this regression-guards that assumption explicitly — an unsigned token must never pass."""
    import jwt as pyjwt

    claims = default_claims()
    unsigned = pyjwt.encode(claims, key="", algorithm="none")

    with pytest.raises(TokenValidationError):
        await _validator().validate(unsigned)


# ---------------------------------------------------------------------------
# 2. Real HTTP behavior through the FastAPI app
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _override_token_validator():
    app.dependency_overrides[get_token_validator] = _validator
    yield
    app.dependency_overrides.pop(get_token_validator, None)


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_post_chat_without_authentication_returns_401() -> None:
    response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_get_conversations_without_authentication_returns_401() -> None:
    response = client.get("/conversations")

    assert response.status_code == 401


def test_get_conversation_by_id_without_authentication_returns_401() -> None:
    response = client.get("/conversations/some-id")

    assert response.status_code == 401


def test_malformed_authorization_header_returns_401() -> None:
    response = client.post(
        "/chat", json={"message": "hello"}, headers={"Authorization": "NotBearer abc123"}
    )

    assert response.status_code == 401


def test_post_chat_with_a_valid_token_is_accepted() -> None:
    token = mint_token(default_claims())

    response = client.post("/chat", json={"message": "hello"}, headers=_auth_header(token))

    assert response.status_code == 200


def test_post_chat_with_an_invalid_token_returns_401() -> None:
    response = client.post(
        "/chat", json={"message": "hello"}, headers=_auth_header("not-a-real-jwt")
    )

    assert response.status_code == 401


def test_post_chat_with_an_expired_token_returns_401() -> None:
    token = mint_expired_token()

    response = client.post("/chat", json={"message": "hello"}, headers=_auth_header(token))

    assert response.status_code == 401


def test_post_chat_with_a_wrong_audience_token_returns_401() -> None:
    token = mint_wrong_audience_token()

    response = client.post("/chat", json={"message": "hello"}, headers=_auth_header(token))

    assert response.status_code == 401


def test_post_chat_with_the_legacy_application_id_uri_audience_returns_401() -> None:
    """PBI-11-01D: end-to-end HTTP regression for the exact live bug this PBI fixes."""
    token = mint_application_id_uri_audience_token()

    response = client.post("/chat", json={"message": "hello"}, headers=_auth_header(token))

    assert response.status_code == 401


def test_post_chat_with_a_malformed_issuer_token_returns_401() -> None:
    token = mint_malformed_issuer_token()

    response = client.post("/chat", json={"message": "hello"}, headers=_auth_header(token))

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 3. IDOR regression + identity isolation — the core PBI-11-01 requirement
# ---------------------------------------------------------------------------


def test_user_b_cannot_read_user_as_conversation_even_supplying_user_as_old_userid() -> None:
    """User A creates a conversation while authenticated. User B, authenticated as a genuinely
    different Entra identity, then requests it back via GET /conversations/{id} — supplying
    User A's OLD (pre-auth-era, now-deprecated) userId string as the `userId` query param, and
    User A's real conversationId. This must still fail: identity comes from the token, never
    from client-supplied userId."""
    user_a_oid = "aaaaaaaa-0000-0000-0000-000000000001"
    user_a_old_userid = "web-user-legacy-victim-id"
    token_a = mint_token(default_claims(oid=user_a_oid))

    create_response = client.post(
        "/chat",
        json={"message": "I need to report a claim", "userId": user_a_old_userid},
        headers=_auth_header(token_a),
    )
    assert create_response.status_code == 200
    conversation_id = create_response.json()["conversationId"]

    # Sanity check: User A herself can read it back.
    self_read = client.get(
        f"/conversations/{conversation_id}",
        params={"userId": user_a_old_userid},
        headers=_auth_header(token_a),
    )
    assert self_read.status_code == 200

    user_b_oid = "bbbbbbbb-0000-0000-0000-000000000002"
    token_b = mint_token(default_claims(oid=user_b_oid))

    attack_response = client.get(
        f"/conversations/{conversation_id}",
        params={"userId": user_a_old_userid},  # attacker supplies the victim's old userId
        headers=_auth_header(token_b),
    )

    assert attack_response.status_code == 404


def test_user_b_conversation_list_never_includes_user_as_conversations() -> None:
    """Identity isolation: even supplying User A's userId as a query param, User B's own
    authenticated identity governs which conversations are listed."""
    user_a_oid = "aaaaaaaa-0000-0000-0000-000000000003"
    user_a_old_userid = "web-user-legacy-victim-id-2"
    token_a = mint_token(default_claims(oid=user_a_oid))
    client.post(
        "/chat",
        json={"message": "I want to check my commissions", "userId": user_a_old_userid},
        headers=_auth_header(token_a),
    )

    user_b_oid = "bbbbbbbb-0000-0000-0000-000000000004"
    token_b = mint_token(default_claims(oid=user_b_oid))

    listing = client.get(
        "/conversations", params={"userId": user_a_old_userid}, headers=_auth_header(token_b)
    )

    assert listing.status_code == 200
    assert listing.json() == []


def test_two_different_authenticated_identities_get_independent_conversation_histories() -> None:
    token_a = mint_token(default_claims(oid="aaaaaaaa-0000-0000-0000-000000000005"))
    token_b = mint_token(default_claims(oid="bbbbbbbb-0000-0000-0000-000000000006"))

    client.post("/chat", json={"message": "hola de A"}, headers=_auth_header(token_a))
    client.post("/chat", json={"message": "hola de B"}, headers=_auth_header(token_b))
    client.post("/chat", json={"message": "otra vez A"}, headers=_auth_header(token_a))

    list_a = client.get("/conversations", headers=_auth_header(token_a)).json()
    list_b = client.get("/conversations", headers=_auth_header(token_b)).json()

    assert len(list_a) == 2
    assert len(list_b) == 1

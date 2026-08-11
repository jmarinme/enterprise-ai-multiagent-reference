"""Validates a Microsoft Entra ID v2.0 access token issued for this API.

Multi-tenant (/common) issuer handling: this platform's App Registration uses the /common
authority intentionally, to support both internal and external (any-organization) users
(PBI-11-01). Under /common there is no single fixed tenant, so there is no single fixed
`iss` value to compare against — Microsoft's own guidance for multi-tenant apps is to
dynamically validate the issuer per token instead of hardcoding one
(https://learn.microsoft.com/azure/active-directory/develop/id-tokens#validating-tokens).

This validates that `iss` matches the standard v2.0 template for the token's OWN `tid`
claim — i.e., the issuer must be self-consistent with the tenant that actually signed the
token. This is a real, positive check (a forged or cross-tenant-mismatched `iss` is rejected),
not a weakened/disabled one — it is simply parameterized by the token's own tenant rather
than a single constant, which is what "correct" issuer validation means for a /common
authority.
"""

from __future__ import annotations

import json

import jwt
from jwt import PyJWTError
from jwt.algorithms import RSAAlgorithm

from api.auth.exceptions import TokenValidationError
from api.auth.jwks import JwksProvider
from api.auth.models import AuthenticatedUser

_ISSUER_TEMPLATE = "https://login.microsoftonline.com/{tid}/v2.0"
_ALGORITHM = "RS256"
# Standard small allowance for clock drift between this server and Microsoft's token issuance
# time — not a weakening of expiry validation, only tolerance for real clock skew.
_LEEWAY_SECONDS = 60


class EntraTokenValidator:
    """Validates signature, expiry, audience, and a tenant-self-consistent issuer for a
    Microsoft Entra ID v2.0 access token. Raises TokenValidationError for any failure; never
    silently downgrades a check."""

    def __init__(self, *, audience: str, jwks_provider: JwksProvider) -> None:
        self._audience = audience
        self._jwks_provider = jwks_provider

    async def validate(self, token: str) -> AuthenticatedUser:
        kid = self._get_kid(token)
        signing_key = await self._resolve_signing_key(kid)
        claims = self._decode_and_verify(token, signing_key)
        self._verify_issuer(claims)
        return self._to_authenticated_user(claims)

    def _get_kid(self, token: str) -> str:
        try:
            header = jwt.get_unverified_header(token)
        except PyJWTError as exc:
            raise TokenValidationError("malformed token header") from exc
        kid = header.get("kid")
        if not kid:
            raise TokenValidationError("token header is missing kid")
        return str(kid)

    async def _resolve_signing_key(self, kid: str) -> RSAAlgorithm:
        keys = await self._jwks_provider.get_keys()
        jwk = _find_jwk(keys, kid)
        if jwk is None:
            # Not found in the cached set — could be genuine key rotation. Refresh once
            # before giving up, rather than either trusting a stale cache indefinitely or
            # refetching on every single request.
            keys = await self._jwks_provider.get_keys(force_refresh=True)
            jwk = _find_jwk(keys, kid)
        if jwk is None:
            raise TokenValidationError("no matching signing key found for this token")
        try:
            return RSAAlgorithm.from_jwk(json.dumps(jwk))  # type: ignore[return-value]
        except (ValueError, TypeError) as exc:
            raise TokenValidationError("signing key is malformed") from exc

    def _decode_and_verify(self, token: str, signing_key: RSAAlgorithm) -> dict:
        try:
            claims: dict = jwt.decode(
                token,
                key=signing_key,  # type: ignore[arg-type]
                algorithms=[_ALGORITHM],
                audience=self._audience,
                leeway=_LEEWAY_SECONDS,
                options={
                    "require": ["exp", "iat", "iss", "aud", "sub"],
                    # Signature, audience, and expiry are verified by PyJWT itself above.
                    # Issuer is verified separately below (per-tenant, not a fixed string —
                    # PyJWT's built-in `issuer=` check only supports one constant value,
                    # which cannot express "any tenant, but self-consistently").
                    "verify_iss": False,
                },
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenValidationError("token has expired") from exc
        except jwt.InvalidAudienceError as exc:
            raise TokenValidationError("token audience does not match this API") from exc
        except jwt.InvalidSignatureError as exc:
            raise TokenValidationError("token signature is invalid") from exc
        except PyJWTError as exc:
            raise TokenValidationError("token failed validation") from exc
        return claims

    def _verify_issuer(self, claims: dict) -> None:
        tid = claims.get("tid")
        iss = claims.get("iss")
        if not tid or not iss:
            raise TokenValidationError("token is missing tid/iss claims required for issuer validation")
        expected_issuer = _ISSUER_TEMPLATE.format(tid=tid)
        if iss != expected_issuer:
            raise TokenValidationError("token issuer is not self-consistent with its own tenant")

    def _to_authenticated_user(self, claims: dict) -> AuthenticatedUser:
        oid = claims.get("oid")
        tid = claims.get("tid")
        if not oid or not tid:
            raise TokenValidationError("token is missing required oid/tid claims")
        return AuthenticatedUser(
            user_id=f"{tid}:{oid}",
            oid=str(oid),
            tid=str(tid),
            name=claims.get("name"),
            email=claims.get("preferred_username") or claims.get("email"),
        )


def _find_jwk(keys: dict, kid: str) -> dict | None:
    for jwk in keys.get("keys", []):
        if jwk.get("kid") == kid:
            return jwk
    return None

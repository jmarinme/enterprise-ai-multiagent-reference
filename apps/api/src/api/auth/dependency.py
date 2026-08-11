"""FastAPI dependency requiring a valid Entra ID Bearer token — the sole source of
authorization identity for every protected route (PBI-11-01). No client-supplied identity
field (a request body's/query's `userId`) is ever consulted here or by any caller of this
dependency.
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from api.auth.exceptions import TokenValidationError
from api.auth.jwks import JwksProvider
from api.auth.models import AuthenticatedUser
from api.auth.validator import EntraTokenValidator
from config.settings import get_settings

_WWW_AUTHENTICATE_HEADER = {"WWW-Authenticate": "Bearer"}

# One process-wide JwksProvider instance (its own internal cache, per-process — matching the
# rest of this codebase's caching posture). Not a Depends() itself: get_token_validator below
# is the overridable seam for tests, per this codebase's provider-abstraction pattern.
_jwks_provider = JwksProvider()


def get_token_validator() -> EntraTokenValidator:
    """Builds the token validator from current settings. A FastAPI dependency itself (not a
    bare module-level singleton) so tests can override it via app.dependency_overrides,
    exactly like every other provider in this codebase (apps/api/src/api/dependencies.py)."""
    settings = get_settings()
    return EntraTokenValidator(audience=settings.entra_api_audience, jwks_provider=_jwks_provider)


async def get_current_user(
    authorization: str | None = Header(default=None),
    validator: EntraTokenValidator = Depends(get_token_validator),
) -> AuthenticatedUser:
    """Requires `Authorization: Bearer <token>`, validates it, and returns the authenticated
    identity. Raises HTTP 401 for a missing header, a malformed header, or any token
    validation failure (bad signature, expired, wrong audience, inconsistent issuer, missing
    required claims) — never a distinguishing error message, so a caller cannot use error
    text to probe why a token was rejected."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid Bearer token is required",
            headers=_WWW_AUTHENTICATE_HEADER,
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid Bearer token is required",
            headers=_WWW_AUTHENTICATE_HEADER,
        )

    try:
        return await validator.validate(token)
    except TokenValidationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers=_WWW_AUTHENTICATE_HEADER,
        ) from None

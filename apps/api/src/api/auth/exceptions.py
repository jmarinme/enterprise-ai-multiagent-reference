"""Exceptions for Entra ID token validation."""

from __future__ import annotations


class TokenValidationError(Exception):
    """Raised for any reason a bearer token is rejected (bad signature, expired, wrong
    audience, malformed/inconsistent issuer, missing required claims, no matching signing
    key). The message is a short, generic category — never the raw token or raw claims
    (CLAUDE.md §10: no sensitive content in logs/errors). Always mapped to HTTP 401 by
    api.auth.dependency.get_current_user."""

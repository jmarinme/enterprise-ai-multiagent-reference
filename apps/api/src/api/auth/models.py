"""Authenticated identity derived from a validated Entra ID token."""

from __future__ import annotations

from pydantic import BaseModel


class AuthenticatedUser(BaseModel):
    """The caller's identity, as proven by a validated Entra ID access token.

    Only api.auth.dependency.get_current_user constructs this — it must never be built from
    client-supplied request data. user_id is the stable, tenant-qualified authorization key
    ("{tid}:{oid}") used as the Cosmos partition key for every conversation read/write;
    name/email are informational only (display purposes), never used for authorization
    (PBI-11-01 requirement: prefer the Entra object identifier over email).
    """

    user_id: str
    oid: str
    tid: str
    name: str | None = None
    email: str | None = None

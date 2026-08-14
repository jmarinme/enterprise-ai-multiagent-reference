"""Authenticated identity derived from a validated Entra ID token."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
    # PBI-13-01: the token's `roles` claim, if present — App Roles are NOT configured on this
    # platform's Entra App Registration today (nothing assigns a real value to this claim yet),
    # so this is always an empty list in practice until a future PBI activates App Roles. Parsed
    # now, ahead of activation, purely so OBSERVABILITY_ACCESS_MODE=roles (prepared but not
    # activated — see apps/api/src/config/settings.py ObservabilityAccessSettings) has a real,
    # already-wired claim to read the moment it is turned on, with zero further token-parsing
    # changes required.
    roles: list[str] = Field(default_factory=list)

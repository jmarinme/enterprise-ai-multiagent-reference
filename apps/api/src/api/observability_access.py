"""Centralized authorization for the Observability feature (PBI-13-01 §16).

Anonymous users never reach this dependency at all — it always runs after
api.auth.dependency.get_current_user, which already raises HTTP 401 for a missing/invalid
token. This dependency only decides, for an already-authenticated caller, whether they may see
Observability data:

- OBSERVABILITY_ACCESS_MODE=all_authenticated (V1 default): every authenticated user passes.
- OBSERVABILITY_ACCESS_MODE=roles (prepared, not activated by this codebase — no Entra App
  Role is created or assigned anywhere in this repo): the validated token's own `roles` claim
  must intersect OBSERVABILITY_ALLOWED_ROLES, or this raises HTTP 403 — enforced here so a
  direct URL/API call can never bypass the frontend's own nav-hiding (CLAUDE.md §16's backend
  requirement: "return HTTP 403 even if the user enters the URL/API directly").
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status

from api.auth.dependency import get_current_user
from api.auth.models import AuthenticatedUser
from config.settings import Settings, get_settings


async def require_observability_access(
    current_user: AuthenticatedUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    if settings.observability_access_mode == "all_authenticated":
        return current_user

    allowed_roles = set(settings.observability_allowed_roles_list)
    if allowed_roles.intersection(current_user.roles):
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Observability access requires one of the configured allowed roles.",
    )

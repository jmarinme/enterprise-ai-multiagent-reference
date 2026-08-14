"""Unit tests for api.observability_access.require_observability_access (PBI-13-01 §16):
all_authenticated passes any authenticated user; roles mode (prepared, never activated by this
codebase) rejects a user without an allowed role with HTTP 403 and accepts one with an allowed
role. Anonymous access is covered separately — this dependency only ever runs after
get_current_user already raised 401 for a missing/invalid token (see test_observability_routes.py
for the end-to-end 401 case).
"""

import pytest
from api.auth.models import AuthenticatedUser
from api.observability_access import require_observability_access
from fastapi import HTTPException

from config.settings import Settings


def _user(roles: list[str] | None = None) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="tid-1:oid-1", oid="oid-1", tid="tid-1", roles=roles or []
    )


async def test_all_authenticated_mode_admits_any_authenticated_user() -> None:
    settings = Settings(observability_access_mode="all_authenticated")

    result = await require_observability_access(current_user=_user(), settings=settings)

    assert result.user_id == "tid-1:oid-1"


async def test_roles_mode_rejects_a_user_without_an_allowed_role() -> None:
    settings = Settings(
        observability_access_mode="roles",
        observability_allowed_roles="Observability.Admin,Observability.Support",
    )

    with pytest.raises(HTTPException) as exc_info:
        await require_observability_access(current_user=_user(roles=["SomeOtherRole"]), settings=settings)

    assert exc_info.value.status_code == 403


async def test_roles_mode_rejects_a_user_with_no_roles_at_all() -> None:
    settings = Settings(observability_access_mode="roles")

    with pytest.raises(HTTPException) as exc_info:
        await require_observability_access(current_user=_user(roles=[]), settings=settings)

    assert exc_info.value.status_code == 403


async def test_roles_mode_admits_a_user_with_an_allowed_role() -> None:
    settings = Settings(
        observability_access_mode="roles",
        observability_allowed_roles="Observability.Admin,Observability.Support",
    )

    result = await require_observability_access(
        current_user=_user(roles=["Observability.Support"]), settings=settings
    )

    assert result.user_id == "tid-1:oid-1"

"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the API, sourced from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "local"
    project_name: str = "tmx-enterprise-ai-reference-platform"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"
    api_version: str = "0.1.0"
    # cors_allowed_origins (PBI-04-02): comma-separated origins, never "*" — the Web app is the
    # only real caller today. Configuration-driven per environment: docker-compose/local dev
    # default to the local Vite preview port; ops/bicep/main.bicep sets this to the deployed
    # Web Container App's own FQDN (resolved dynamically, never hardcoded) for DEV/staging/prod.
    cors_allowed_origins: str = "http://localhost:3000"

    # Entra ID (Azure AD) authentication — PBI-11-01. Defaults match the confirmed DEV App
    # Registration (a Single Page Application registration supporting internal and external
    # users, hence /common rather than a fixed tenant — CLAUDE.md §4.5). None of these values
    # are secrets — a SPA client ID, an authority URL, and an Application ID URI are all meant
    # to be public — so, consistent with this class's existing pattern (e.g. cosmos_db_database
    # above), they default to the real, current values rather than an empty placeholder, while
    # remaining overridable per environment via env vars.
    entra_authority: str = "https://login.microsoftonline.com/common"
    entra_client_id: str = "67d95215-5a31-416a-99ab-5fe203fb7c32"
    # PBI-11-01D: the expected `aud` claim on incoming access tokens — confirmed against a real,
    # live Entra v2.0 token from this exact App Registration (ver=2.0, scp=access_as_user).
    # For a v2.0 access token, `aud` is the bare API client ID GUID, never the "api://..."
    # Application ID URI — that URI is the *resource identifier requested by the frontend*
    # (src/auth/loginRequest.ts's scope, api://67d95215-.../access_as_user) and appears in the
    # `scp`-granting request, but Entra issues the v2.0 token itself with `aud` set to the bare
    # GUID. This platform issues only v2.0 tokens (no v1 support exists or is planned), so a
    # single exact-match audience is correct — do not add "api://..." as a second accepted
    # value without a proven, live v1-token requirement.
    entra_api_audience: str = "67d95215-5a31-416a-99ab-5fe203fb7c32"

    # Observability access control (PBI-13-01 §16). V1 default is all_authenticated: any
    # authenticated user may view every conversation's business/agentic observability data —
    # a deliberate, disclosed V1 design choice (see docs/Architecture/observability.md), not an
    # oversight. `roles` mode is prepared but never activated by this codebase itself — no
    # Entra App Role is created or assigned; switching this value only changes which branch of
    # apps/api/src/api/observability_access.py's dependency executes.
    observability_enabled: bool = True
    observability_access_mode: Literal["all_authenticated", "roles"] = "all_authenticated"
    observability_allowed_roles: str = (
        "Observability.Admin,Observability.Support,Observability.Auditor"
    )

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        """Parsed, whitespace-trimmed origin list — empty entries dropped."""
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def observability_allowed_roles_list(self) -> list[str]:
        """Parsed, whitespace-trimmed allowed-roles list — empty entries dropped."""
        return [
            role.strip() for role in self.observability_allowed_roles.split(",") if role.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance for dependency injection."""
    return Settings()

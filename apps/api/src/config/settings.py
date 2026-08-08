"""Application configuration loaded from environment variables."""

from functools import lru_cache

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

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        """Parsed, whitespace-trimmed origin list — empty entries dropped."""
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance for dependency injection."""
    return Settings()

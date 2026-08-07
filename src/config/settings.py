"""Configuration for the reusable src/ domain library. Distinct from apps/api's own
apps/api/src/config/settings.py, which configures the API transport layer specifically.
"""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class ConversationStoreSettings(BaseSettings):
    """Selects and configures the ConversationRepository implementation.

    Defaults to the in-memory provider so local development and unit tests never require
    Azure or Cosmos DB connectivity.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    conversation_store_provider: Literal["in_memory", "cosmos"] = "in_memory"
    cosmos_db_endpoint: str | None = None
    cosmos_db_database: str = "tmxai-conversation-db"
    cosmos_db_container: str = "conversations"

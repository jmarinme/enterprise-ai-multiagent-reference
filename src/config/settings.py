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


class SecretProviderSettings(BaseSettings):
    """Selects and configures the SecretProvider implementation.

    Defaults to the environment-variable provider so local development and unit tests never
    require Azure or Key Vault connectivity.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    secret_provider: Literal["environment", "key_vault"] = "environment"
    key_vault_uri: str | None = None


class LLMSettings(BaseSettings):
    """Selects and configures the LLMProvider implementation.

    Defaults to the mock provider so local development and unit tests never require Azure
    OpenAI connectivity. Entra ID (DefaultAzureCredential) authentication is preferred for the
    azure_openai provider; azure_openai_use_api_key opts into API-key auth instead, in which
    case the key is read via SecretProvider (see apps/api/src/api/dependencies.py), never
    directly from the environment inside the provider itself.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_provider: Literal["mock", "azure_openai"] = "mock"
    azure_openai_endpoint: str | None = None
    azure_openai_deployment: str | None = None
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_use_api_key: bool = False
    azure_openai_api_key_secret_name: str = "azure-openai-api-key"

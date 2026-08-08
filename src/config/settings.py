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
    cosmos_db_database: str = "tmxap-conversation-db"
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
    OpenAI or Ollama connectivity. Entra ID (DefaultAzureCredential) authentication is
    preferred for the azure_openai provider; azure_openai_use_api_key opts into API-key auth
    instead, in which case the key is read via SecretProvider (see
    apps/api/src/api/dependencies.py), never directly from the environment inside the provider
    itself.

    ollama_base_url defaults to a plain host-local Ollama install (`http://localhost:11434`).
    When the API runs inside Docker on Windows/Mac and Ollama runs on the host, set
    OLLAMA_BASE_URL=http://host.docker.internal:11434 in `.env` — this is a deployment/runtime
    configuration choice, never hardcoded here (PBI-03-01).
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_provider: Literal["mock", "azure_openai", "ollama"] = "mock"
    azure_openai_endpoint: str | None = None
    azure_openai_deployment: str | None = None
    # azure_openai_model_name (PBI-03-05): the underlying model (e.g. "gpt-5-mini"), distinct
    # from azure_openai_deployment (an arbitrary alias, e.g. "chat"). AzureOpenAIProvider needs
    # this separately to detect reasoning-family model capability differences. None falls back
    # to azure_openai_deployment (see apps/api/src/api/dependencies.py) so a caller/environment
    # that never sets it behaves exactly as before this PBI.
    azure_openai_model_name: str | None = None
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_use_api_key: bool = False
    azure_openai_api_key_secret_name: str = "azure-openai-api-key"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    ollama_timeout_seconds: float = 60.0


class ToolCallingSettings(BaseSettings):
    """Configures the Tool Calling orchestration framework (src.core.tool_calling, PBI-02-04).

    tool_calling_max_iterations is the loop's safety cap (CLAUDE.md §9 "resilience is
    explicit"): a conservative default that comfortably covers a typical "look something up,
    then answer" round trip while still bounding a misbehaving LLM that always requests
    another tool call.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    tool_calling_max_iterations: int = 3


class KnowledgeSettings(BaseSettings):
    """Selects and configures the KnowledgeProvider implementation.

    Defaults to the local provider so local development and unit tests never require Azure AI
    Search connectivity. Entra ID (DefaultAzureCredential) authentication is preferred for the
    azure_ai_search provider; azure_ai_search_use_api_key opts into API-key auth instead, in
    which case the key is read via SecretProvider (see apps/api/src/api/dependencies.py), never
    directly from the environment inside the provider itself.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    knowledge_provider: Literal["local", "azure_ai_search"] = "local"
    azure_ai_search_endpoint: str | None = None
    azure_ai_search_index_name: str | None = None
    azure_ai_search_use_api_key: bool = False
    azure_ai_search_api_key_secret_name: str = "azure-ai-search-api-key"

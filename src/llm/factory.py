"""Selects an LLMProvider implementation from configuration.

AzureOpenAIProvider and OllamaLLMProvider are imported lazily, inside their own branches, so
the default mock provider never requires the openai/azure-identity/aiohttp packages to be
installed or reachable — same pattern as src.services.conversation_store.factory and
src.services.secret_store.factory.
"""

from __future__ import annotations

from src.config.settings import LLMSettings
from src.domain.secret_provider import SecretProvider
from src.llm.mock_provider import MockLLMProvider
from src.llm.provider import LLMProvider


def get_llm_provider(
    settings: LLMSettings, secret_provider: SecretProvider | None = None
) -> LLMProvider:
    """Return the LLMProvider implementation selected by settings."""
    if settings.llm_provider == "mock":
        return MockLLMProvider()

    if settings.llm_provider == "azure_openai":
        from src.llm.azure_openai_provider import AzureOpenAIProvider

        use_api_key = settings.azure_openai_use_api_key
        return AzureOpenAIProvider(
            endpoint=settings.azure_openai_endpoint or "",
            deployment=settings.azure_openai_deployment or "",
            api_version=settings.azure_openai_api_version,
            secret_provider=secret_provider if use_api_key else None,
            api_key_secret_name=settings.azure_openai_api_key_secret_name if use_api_key else None,
            # model_name (PBI-03-05): the real underlying model, distinct from
            # azure_openai_deployment's arbitrary alias — see AzureOpenAIProvider.__init__ and
            # docs/sprint_03/decisions.md. None (unset) falls back to the deployment alias
            # itself, matching this factory's pre-PBI-03-05 behavior exactly.
            model_name=settings.azure_openai_model_name,
        )

    if settings.llm_provider == "ollama":
        from src.llm.ollama_provider import OllamaLLMProvider

        return OllamaLLMProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout_seconds=settings.ollama_timeout_seconds,
        )

    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")

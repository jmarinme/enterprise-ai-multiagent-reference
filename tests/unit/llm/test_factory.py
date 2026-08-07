"""Unit tests for get_llm_provider: provider selection."""

import pytest

from src.config.settings import LLMSettings
from src.llm.exceptions import LLMConfigurationError
from src.llm.factory import get_llm_provider
from src.llm.mock_provider import MockLLMProvider


def test_factory_returns_mock_provider_by_default() -> None:
    settings = LLMSettings()

    provider = get_llm_provider(settings)

    assert isinstance(provider, MockLLMProvider)


def test_factory_returns_azure_openai_provider_when_configured() -> None:
    from src.llm.azure_openai_provider import AzureOpenAIProvider

    settings = LLMSettings(
        llm_provider="azure_openai",
        azure_openai_endpoint="https://example.openai.azure.com/",
        azure_openai_deployment="gpt-4o-mini",
    )

    provider = get_llm_provider(settings)

    assert isinstance(provider, AzureOpenAIProvider)


def test_factory_azure_openai_missing_endpoint_raises_configuration_error() -> None:
    """PBI-03-02: missing Azure configuration must fail safely, through the factory (not just
    when AzureOpenAIProvider is constructed directly)."""
    settings = LLMSettings(llm_provider="azure_openai", azure_openai_deployment="gpt-4o-mini")

    with pytest.raises(LLMConfigurationError):
        get_llm_provider(settings)


def test_factory_returns_ollama_provider_when_configured() -> None:
    from src.llm.ollama_provider import OllamaLLMProvider

    settings = LLMSettings(
        llm_provider="ollama",
        ollama_base_url="http://localhost:11434",
        ollama_model="llama3.1",
    )

    provider = get_llm_provider(settings)

    assert isinstance(provider, OllamaLLMProvider)


def test_factory_raises_for_unsupported_provider() -> None:
    settings = LLMSettings.model_construct(llm_provider="unsupported")

    try:
        get_llm_provider(settings)
    except ValueError as exc:
        assert "Unsupported LLM provider" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported provider")

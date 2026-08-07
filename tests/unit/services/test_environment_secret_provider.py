"""Unit tests for EnvironmentSecretProvider: successful retrieval and missing-variable behavior."""

import pytest

from src.domain.secret_provider import SecretNotFoundError
from src.services.secret_store.environment import EnvironmentSecretProvider


async def test_returns_value_when_env_var_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "local-dev-placeholder-value")
    provider = EnvironmentSecretProvider()

    result = await provider.get_secret("azure-openai-api-key")

    assert result == "local-dev-placeholder-value"


async def test_raises_secret_not_found_when_env_var_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    provider = EnvironmentSecretProvider()

    with pytest.raises(SecretNotFoundError):
        await provider.get_secret("azure-openai-api-key")


async def test_raises_secret_not_found_when_env_var_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "")
    provider = EnvironmentSecretProvider()

    with pytest.raises(SecretNotFoundError):
        await provider.get_secret("azure-openai-api-key")

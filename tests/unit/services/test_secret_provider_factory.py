"""Unit tests for get_secret_provider: provider selection and configuration validation."""

import pytest
from pydantic import ValidationError

from src.config.settings import SecretProviderSettings
from src.services.secret_store.environment import EnvironmentSecretProvider
from src.services.secret_store.factory import get_secret_provider


def test_factory_returns_environment_provider_by_default() -> None:
    settings = SecretProviderSettings()

    provider = get_secret_provider(settings)

    assert isinstance(provider, EnvironmentSecretProvider)


def test_factory_returns_key_vault_provider_when_configured() -> None:
    from src.services.secret_store.key_vault import AzureKeyVaultSecretProvider

    settings = SecretProviderSettings(
        secret_provider="key_vault", key_vault_uri="https://example.vault.azure.net/"  # pragma: allowlist secret -- example.vault.azure.net placeholder, not a real URI
    )

    provider = get_secret_provider(settings)

    assert isinstance(provider, AzureKeyVaultSecretProvider)


def test_factory_raises_when_key_vault_selected_without_uri() -> None:
    settings = SecretProviderSettings(secret_provider="key_vault", key_vault_uri=None)

    with pytest.raises(ValueError, match="KEY_VAULT_URI"):
        get_secret_provider(settings)


def test_settings_reject_unsupported_provider_value() -> None:
    with pytest.raises(ValidationError):
        SecretProviderSettings(secret_provider="bogus")  # type: ignore[arg-type]

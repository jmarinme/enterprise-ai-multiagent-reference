"""Selects a SecretProvider implementation from configuration.

The Key Vault adapter is imported lazily, inside the key_vault branch, so the default
environment-variable provider never requires azure-identity/azure-keyvault-secrets to be
installed or reachable.
"""

from __future__ import annotations

from src.config.settings import SecretProviderSettings
from src.domain.secret_provider import SecretProvider
from src.services.secret_store.environment import EnvironmentSecretProvider


def get_secret_provider(settings: SecretProviderSettings) -> SecretProvider:
    """Return the SecretProvider implementation selected by settings."""
    if settings.secret_provider == "environment":
        return EnvironmentSecretProvider()

    if settings.secret_provider == "key_vault":
        from src.services.secret_store.key_vault import AzureKeyVaultSecretProvider

        if not settings.key_vault_uri:
            raise ValueError("KEY_VAULT_URI must be set when SECRET_PROVIDER=key_vault")
        return AzureKeyVaultSecretProvider(vault_uri=settings.key_vault_uri)

    raise ValueError(f"Unsupported secret provider: {settings.secret_provider}")

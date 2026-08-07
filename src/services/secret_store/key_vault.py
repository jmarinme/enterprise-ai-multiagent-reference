"""Azure Key Vault adapter for SecretProvider.

Authenticates with Azure AD via DefaultAzureCredential (Managed Identity-compatible) — no
keys or connection strings, consistent with the platform's Key Vault Bicep module (RBAC-only
authorization; see ops/bicep/modules/key-vault.bicep).

Not imported by the local-development path; only reached via src.services.secret_store.factory
when SECRET_PROVIDER=key_vault. Never reads or stores real secret values as part of this
codebase — only implements the retrieval mechanism.
"""

from __future__ import annotations

from azure.core.exceptions import ResourceNotFoundError
from azure.identity.aio import DefaultAzureCredential
from azure.keyvault.secrets.aio import SecretClient

from src.domain.secret_provider import SecretNotFoundError


class AzureKeyVaultSecretProvider:
    """SecretProvider implementation backed by Azure Key Vault."""

    def __init__(self, vault_uri: str) -> None:
        self._credential = DefaultAzureCredential()
        self._client = SecretClient(vault_url=vault_uri, credential=self._credential)

    async def close(self) -> None:
        await self._client.close()
        await self._credential.close()

    async def get_secret(self, secret_name: str) -> str:
        try:
            secret = await self._client.get_secret(secret_name)
        except ResourceNotFoundError as exc:
            raise SecretNotFoundError(secret_name) from exc
        if secret.value is None:
            raise SecretNotFoundError(secret_name)
        return secret.value

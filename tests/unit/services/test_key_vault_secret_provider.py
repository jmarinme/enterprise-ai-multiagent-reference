"""Unit tests for AzureKeyVaultSecretProvider, fully mocked — no Azure connectivity.

Never reads or stores a real secret value; all Key Vault SDK objects are mocked.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.secret_provider import SecretNotFoundError


@patch("src.services.secret_store.key_vault.DefaultAzureCredential")
@patch("src.services.secret_store.key_vault.SecretClient")
async def test_get_secret_returns_value_on_success(
    mock_secret_client_cls: MagicMock, mock_credential_cls: MagicMock
) -> None:
    from src.services.secret_store.key_vault import AzureKeyVaultSecretProvider

    mock_client = mock_secret_client_cls.return_value
    mock_secret = MagicMock()
    mock_secret.value = "mock-secret-value"
    mock_client.get_secret = AsyncMock(return_value=mock_secret)

    provider = AzureKeyVaultSecretProvider(vault_uri="https://example.vault.azure.net/")
    result = await provider.get_secret("azure-openai-api-key")

    assert result == "mock-secret-value"
    mock_client.get_secret.assert_awaited_once_with("azure-openai-api-key")


@patch("src.services.secret_store.key_vault.DefaultAzureCredential")
@patch("src.services.secret_store.key_vault.SecretClient")
async def test_get_secret_raises_secret_not_found_when_missing(
    mock_secret_client_cls: MagicMock, mock_credential_cls: MagicMock
) -> None:
    from azure.core.exceptions import ResourceNotFoundError

    from src.services.secret_store.key_vault import AzureKeyVaultSecretProvider

    mock_client = mock_secret_client_cls.return_value
    mock_client.get_secret = AsyncMock(side_effect=ResourceNotFoundError("not found"))

    provider = AzureKeyVaultSecretProvider(vault_uri="https://example.vault.azure.net/")

    with pytest.raises(SecretNotFoundError):
        await provider.get_secret("missing-secret")


@patch("src.services.secret_store.key_vault.DefaultAzureCredential")
@patch("src.services.secret_store.key_vault.SecretClient")
async def test_get_secret_raises_secret_not_found_when_value_is_none(
    mock_secret_client_cls: MagicMock, mock_credential_cls: MagicMock
) -> None:
    from src.services.secret_store.key_vault import AzureKeyVaultSecretProvider

    mock_client = mock_secret_client_cls.return_value
    mock_secret = MagicMock()
    mock_secret.value = None
    mock_client.get_secret = AsyncMock(return_value=mock_secret)

    provider = AzureKeyVaultSecretProvider(vault_uri="https://example.vault.azure.net/")

    with pytest.raises(SecretNotFoundError):
        await provider.get_secret("disabled-secret")

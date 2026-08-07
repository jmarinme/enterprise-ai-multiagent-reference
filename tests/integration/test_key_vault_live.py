"""Integration test scaffold for AzureKeyVaultSecretProvider.

Skipped entirely unless a real Key Vault URI is configured via KEY_VAULT_URI — this suite
never runs against Azure automatically and requires no Azure connectivity to collect. Also
skipped if the optional Key Vault SDK dependency is not installed.

Only exercises the missing-secret path: it deliberately never reads or stores a real secret
value, so it is safe to run against a live vault without any prior setup.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("azure.keyvault.secrets")

KEY_VAULT_URI = os.environ.get("KEY_VAULT_URI")

pytestmark = pytest.mark.skipif(
    not KEY_VAULT_URI,
    reason="KEY_VAULT_URI is not set; skipping live Azure Key Vault integration test",
)


async def test_missing_secret_raises_against_live_key_vault() -> None:
    from src.domain.secret_provider import SecretNotFoundError
    from src.services.secret_store.key_vault import AzureKeyVaultSecretProvider

    assert KEY_VAULT_URI is not None
    provider = AzureKeyVaultSecretProvider(vault_uri=KEY_VAULT_URI)
    try:
        with pytest.raises(SecretNotFoundError):
            await provider.get_secret("tmx-integration-test-nonexistent-secret-do-not-create")
    finally:
        await provider.close()

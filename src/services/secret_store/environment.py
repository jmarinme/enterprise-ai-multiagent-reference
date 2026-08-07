"""Environment-variable SecretProvider for local development. Requires no Azure connectivity —
the default provider for Sprint 0 local execution.

Secret names use the Key Vault-safe lowercase-hyphen convention (e.g. "azure-openai-api-key");
this adapter maps them to the equivalent upper-snake-case environment variable
(e.g. "AZURE_OPENAI_API_KEY").
"""

from __future__ import annotations

import os

from src.domain.secret_provider import SecretNotFoundError


def _env_var_name(secret_name: str) -> str:
    return secret_name.upper().replace("-", "_")


class EnvironmentSecretProvider:
    """SecretProvider backed by process environment variables."""

    async def get_secret(self, secret_name: str) -> str:
        value = os.environ.get(_env_var_name(secret_name))
        if not value:
            raise SecretNotFoundError(secret_name)
        return value

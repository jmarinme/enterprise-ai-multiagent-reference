"""Abstract contract for secret retrieval. Concrete adapters live under
src/services/secret_store/ (environment variables for local dev, Azure Key Vault for Azure).
"""

from __future__ import annotations

from typing import Protocol


class SecretNotFoundError(Exception):
    """Raised when a requested secret does not exist in the configured provider."""

    def __init__(self, secret_name: str) -> None:
        self.secret_name = secret_name
        super().__init__(f"Secret '{secret_name}' was not found")


class SecretProvider(Protocol):
    """Retrieval contract for configuration secrets (e.g. a future Azure OpenAI API key)."""

    async def get_secret(self, secret_name: str) -> str:
        """Return the value of secret_name, or raise SecretNotFoundError."""
        ...

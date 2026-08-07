"""PromptProvider Protocol — hides where prompts are stored (filesystem, future Azure Blob
Storage, Git, ...). Agents and PromptManager depend only on this Protocol; they never know
file paths, YAML, Markdown, JSON, Azure, or Git.
"""

from __future__ import annotations

from typing import Protocol

from src.prompts.models import PromptDefinition


class PromptProvider(Protocol):
    """Contract for loading a PromptDefinition by logical identifier."""

    async def load(self, identifier: str) -> PromptDefinition: ...

"""PromptManager: resolves logical identifiers via a PromptProvider, validates the render
context, renders the template, and returns a typed RenderedPrompt (or PromptMetadata alone).
No LLM calls — this framework stops at producing rendered text.
"""

from __future__ import annotations

from src.prompts.exceptions import PromptNotFoundError, PromptValidationError
from src.prompts.models import PromptDefinition, PromptMetadata, PromptRenderContext, RenderedPrompt
from src.prompts.provider import PromptProvider
from src.prompts.renderer import render_template


class PromptManager:
    """The single entry point Agents use to obtain rendered prompts. Hides the PromptProvider
    and every storage detail behind it — Agents never know file paths, YAML, Markdown, or
    Azure."""

    def __init__(self, provider: PromptProvider) -> None:
        self._provider = provider

    async def render(self, identifier: str, context: PromptRenderContext) -> RenderedPrompt:
        """Load, then render, the prompt identified by identifier."""
        definition = await self._load(identifier)
        text = render_template(definition, context)
        return RenderedPrompt(identifier=identifier, text=text, metadata=definition.metadata)

    async def get_metadata(self, identifier: str) -> PromptMetadata:
        """Return only the metadata for a prompt, without rendering it."""
        definition = await self._load(identifier)
        return definition.metadata

    async def _load(self, identifier: str) -> PromptDefinition:
        try:
            return await self._provider.load(identifier)
        except (PromptNotFoundError, PromptValidationError):
            raise
        except Exception as exc:
            # Normalize any unexpected provider failure into a typed exception rather than
            # letting a raw, provider-specific error (e.g. an OSError from a future
            # filesystem/network provider) escape this boundary.
            raise PromptValidationError(identifier, f"Provider failure: {exc}") from exc

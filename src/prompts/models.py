"""Typed models for the Prompt Management framework.

Agent -> PromptManager -> PromptProvider -> PromptDefinition -> Template Renderer ->
RenderedPrompt -> (future LLM adapter).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PromptVersion(BaseModel):
    """Semantic version (MAJOR.MINOR.PATCH) of a prompt definition."""

    major: int
    minor: int
    patch: int

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    @classmethod
    def parse(cls, value: str) -> PromptVersion:
        """Parse a "MAJOR.MINOR.PATCH" string into a PromptVersion."""
        parts = value.strip().split(".")
        if len(parts) != 3 or not all(part.isdigit() for part in parts):
            raise ValueError(f"'{value}' is not a valid MAJOR.MINOR.PATCH version")
        major, minor, patch = (int(part) for part in parts)
        return cls(major=major, minor=minor, patch=patch)


class PromptMetadata(BaseModel):
    """Descriptive metadata for a prompt, independent of its rendered content.

    Mirrors the fields CLAUDE.md §9 requires every prompt to document: name (identifier),
    version, purpose, allowed Tools, prohibited decisions, and change notes.
    """

    identifier: str
    version: PromptVersion
    purpose: str
    allowed_tools: list[str] = Field(default_factory=list)
    prohibited_decisions: list[str] = Field(default_factory=list)
    change_notes: str | None = None
    required_variables: list[str] = Field(default_factory=list)


class PromptDefinition(BaseModel):
    """A loaded, unrendered prompt: its metadata plus the raw template body."""

    metadata: PromptMetadata
    template: str


class PromptRenderContext(BaseModel):
    """Typed variables available to prompt templates. Agents never construct raw strings —
    only this typed context is passed to PromptManager.render()."""

    conversation_id: str | None = None
    user_id: str | None = None
    intent: str | None = None
    conversation_summary: str | None = None
    tool_summaries: list[str] = Field(default_factory=list)
    agent_name: str | None = None


class RenderedPrompt(BaseModel):
    """The final rendered prompt text plus the metadata it was rendered from."""

    identifier: str
    text: str
    metadata: PromptMetadata

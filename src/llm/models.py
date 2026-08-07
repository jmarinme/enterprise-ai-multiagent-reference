"""Typed models for the LLM Adapter framework.

RenderedPrompt (src.prompts.models) -> LLMRequest -> LLMProvider.generate() -> LLMResponse.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class LLMMessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class LLMMessage(BaseModel):
    """A single message in an LLM conversation turn."""

    role: LLMMessageRole
    content: str


class LLMGenerationSettings(BaseModel):
    """Typed, provider-agnostic generation configuration. Never embedded in Agent code —
    Agents construct this from their own defaults or configuration, not the reverse."""

    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=512, gt=0)
    timeout_seconds: float = Field(default=30.0, gt=0)
    model: str | None = None
    """Optional model/deployment identifier override; defaults to the provider's own
    configured deployment when None."""


class LLMRequest(BaseModel):
    """A request to generate a completion."""

    messages: list[LLMMessage]
    settings: LLMGenerationSettings = Field(default_factory=LLMGenerationSettings)
    correlation_id: str | None = None
    conversation_id: str | None = None
    user_id: str | None = None


class LLMUsage(BaseModel):
    """Token usage reported by the provider. May be all zeros for a mock/deterministic
    provider."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMResponse(BaseModel):
    """A generated completion."""

    text: str
    model: str
    usage: LLMUsage = Field(default_factory=LLMUsage)
    correlation_id: str | None = None

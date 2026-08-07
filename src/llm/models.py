"""Typed models for the LLM Adapter framework.

RenderedPrompt (src.prompts.models) -> LLMRequest -> LLMProvider.generate() -> LLMResponse.

Tool Calling (PBI-02-04): LLMToolDefinition/ToolCallRequest/ToolCallArgument are the LLM
*protocol* boundary's own typed contracts — what is sent to, and received from, the LLM
itself (mirroring how OpenAI/Azure OpenAI's own chat-completions API defines `tools`/
`tool_calls` as part of the request/response shape). They live here, not in
src.core.tool_calling, because LLMRequest/LLMResponse need to reference them directly and
src/llm/ must never depend on src/core/ (orchestration sits above, not below, this framework).
The *orchestration* layer's own contracts (ToolCallResult, ToolCallingContext,
ToolCallingResponse) live in src.core.tool_calling.models and depend on these, never the
reverse.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class LLMMessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    # Carries a tool's result back to the LLM after a ToolCallRequest was executed (PBI-02-04).
    TOOL = "tool"


class LLMMessage(BaseModel):
    """A single message in an LLM conversation turn."""

    role: LLMMessageRole
    content: str
    # Set only on a TOOL-role message: correlates this result back to the ToolCallRequest.
    # call_id that produced it. None for every other role — additive, existing SYSTEM/USER/
    # ASSISTANT messages are unaffected.
    tool_call_id: str | None = None


class LLMToolDefinition(BaseModel):
    """One Tool exposed to the LLM as callable, built from a registered Tool's own metadata
    and input_model (src.core.tool_calling.orchestrator.ToolCallingOrchestrator.
    build_tool_definitions) — never hand-authored, so the LLM is never offered a tool name
    that ToolRegistry does not actually recognize."""

    name: str
    description: str
    # JSON schema (from Tool.input_model.model_json_schema()) describing valid arguments.
    # dict[str, Any] is the correct, standard shape for a JSON schema document — the same
    # deliberate, documented exception src.tools.models.ToolRequest.tool_input already makes
    # at the equivalent runtime boundary.
    parameters_schema: dict[str, Any] = Field(default_factory=dict)


class ToolCallArgument(BaseModel):
    """One named argument exactly as the LLM supplied it, before any validation against the
    resolved Tool's own input_model (which remains ToolExecutor's job, never this framework's,
    per CLAUDE.md §3 — the LLM is not the source of truth)."""

    name: str
    value: Any


class ToolCallRequest(BaseModel):
    """The LLM's request to invoke one Tool by name, with typed arguments — never executed
    directly; src.core.tool_calling.orchestrator.ToolCallingOrchestrator is the only component
    authorized to turn this into an actual Tool execution, and only after verifying tool_name
    is both registered and allow-listed for the requesting Agent."""

    call_id: str
    tool_name: str
    arguments: list[ToolCallArgument] = Field(default_factory=list)


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
    # Tools the LLM may request (PBI-02-04). Empty for every existing call site (the shared
    # src.agents.shared.annotation helper never sets this) — additive, zero behavior change.
    tools: list[LLMToolDefinition] = Field(default_factory=list)
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
    # The LLM's requested tool invocations, if any (PBI-02-04). Empty for every existing call
    # site (no provider populates this unless request.tools was non-empty) — additive, zero
    # behavior change.
    tool_calls: list[ToolCallRequest] = Field(default_factory=list)
    correlation_id: str | None = None

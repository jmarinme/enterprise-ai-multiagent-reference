"""Domain models for business/agentic observability (PBI-13-01).

Distinct from apps/api/src/observability/logging.py (technical, Application-Insights-adjacent
logging) — these models capture *what happened in business terms* for one processing run
(intent, routing, tool usage, tokens, cost, outcome), never hidden chain-of-thought
(CLAUDE.md §10). Every field that is not actually available from the current pipeline is
`None`, never fabricated (PBI-13-01 §7: "Never fabricate unavailable telemetry").

Field names are camelCase on the wire (matching src.domain.conversation's convention) via the
same shared alias generator.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

RunStatus = Literal["completed", "needs_data", "escalated", "error", "abandoned"]


def _utcnow() -> datetime:
    return datetime.now(UTC)


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class RunToolCall(_CamelModel):
    """A sanitized, summarized view of one ToolCallResult (src.core.tool_calling.models),
    safe to persist and display — never raw tool input, only whatever
    ObservabilityService.sanitize_tool_call already redacted."""

    call_id: str
    tool_name: str
    success: bool
    error_type: str | None = None
    latency_ms: float | None = None


class RunTokenUsage(_CamelModel):
    """Token usage captured from the ReAct/Tool-Calling loop's own LLM calls (the loop that
    drives business decisions) — not necessarily every adjunct LLM call an Agent makes (e.g. a
    prompt-diagnostics annotation call), which is intentionally out of scope for this metric.
    See docs/Architecture/adr on observability for the exact boundary."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class RunRecord(_CamelModel):
    """One processing run — everything safe to know about how one user message was handled.

    Unavailable data is represented as `None`, never a fabricated value (PBI-13-01 §7). This is
    the Cosmos document schema for the `observability_runs` container, partition key
    `/conversationId`.
    """

    id: str = Field(description="Same value as run_id — Cosmos document id.")
    run_id: str
    conversation_id: str
    message_id: str | None = None
    # Alias of the platform's existing correlation_id (CLAUDE.md §10/§7) — no real OpenTelemetry
    # trace_id exists in this codebase today (Application Insights is provisioned but not
    # instrumented, PBI-13-01 §0 finding #7); never fabricated as a distinct identifier.
    trace_id: str | None = None
    user_id: str
    created_at: datetime = Field(default_factory=_utcnow)

    detected_intent: str | None = None
    intent_confidence: float | None = None
    selected_agent: str | None = None
    routing_reason: str | None = None
    # PBI-14-04: which mechanism actually produced the routing decision
    # ("semantic" | "deterministic_fallback" | "clarification") — never fabricated as "semantic"
    # when the resilience fallback fired. See src.supervisor.semantic_routing.RoutingDecision.
    routing_source: str | None = None
    # True only when the shared turn interpretation flagged genuine cross-domain ambiguity and
    # FallbackAgent asked a clarifying question instead of guessing (see
    # src.agents.fallback_agent). None when routing never reached that decision (e.g. error path).
    requires_clarification: bool | None = None
    # Runner-up intent labels the semantic interpretation considered, in order — empty list (not
    # None) when the call succeeded but found no plausible alternative; None only when routing
    # never completed (e.g. the error path, or the deterministic-fallback path, which never asks
    # the LLM for alternatives at all).
    alternative_intents: list[str] | None = None

    tool_calls: list[RunToolCall] = Field(default_factory=list)

    model: str | None = None
    token_usage: RunTokenUsage | None = None
    estimated_cost_usd: float | None = None
    pricing_snapshot_version: str | None = None

    total_latency_ms: float | None = None
    iterations: int | None = None
    stopped_due_to_max_iterations: bool | None = None
    stopped_due_to_timeout: bool | None = None

    final_status: RunStatus | None = None
    error_category: str | None = None


class ConversationSummary(_CamelModel):
    """Aggregate observability view of one conversation — kept deliberately separate from
    src.domain.conversation.Conversation (the chat persistence document, `conversations`
    container, partition key `/userId`). Lives in the `observability_runs` container instead
    (partition key `/conversationId`, same as RunRecord — see the ADR), so the dashboard never
    has to read or scan the chat container's embedded `messages` arrays (PBI-13-01 §6 "avoid
    expensive full-message scans"), and the core chat read/write path is never touched by this
    feature at all.
    """

    id: str = Field(description="Same value as conversation_id — Cosmos document id.")
    conversation_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    status: str | None = None
    primary_domain: str | None = None
    message_count: int | None = None
    run_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    # PBI-14-03: None means genuinely Unavailable (at least one contributing run had no known
    # model price — src.observability.pricing.PricingCatalog.estimate_cost_usd already returns
    # None for that case) — never coerced to 0.0. Summing only the known-cost runs and calling
    # that a total would silently understate real spend and display a precise-looking but wrong
    # number; once a conversation's total is None it stays None, never resurrected by a later
    # known-cost run (see src.services.observability_store.in_memory/cosmos's record_run).
    total_estimated_cost_usd: float | None = None
    operational_quality_score: float | None = None
    business_outcome: str | None = None
    last_message_preview: str | None = None


class SummaryKpis(_CamelModel):
    """Top dashboard KPIs. Any metric that cannot be calculated from real persisted data is
    `None` ("Unavailable" in the UI) — never a fabricated zero (PBI-13-01 §9)."""

    conversation_count: int | None = None
    run_count: int | None = None
    success_rate: float | None = None
    average_latency_ms: float | None = None
    total_input_tokens: int | None = None
    total_output_tokens: int | None = None
    total_estimated_cost_usd: float | None = None

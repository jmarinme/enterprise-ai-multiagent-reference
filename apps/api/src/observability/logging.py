"""Structured JSON logging configuration for the API.

PBI-14-07: JsonFormatter previously built its output payload from a fixed set of keys only
(timestamp/level/logger/message/correlationId/exception) — every field a caller passed via
Python logging's `extra={...}` mechanism (e.g. src.supervisor.orchestrator's own
"supervisor_turn_latency" event, which sets routingSource/conversationId/agent/... this way) was
silently discarded, never dropped loudly, never raising — a real, previously-undiscovered
observability defect discovered while investigating why a live DEV routing decision could not be
diagnosed from Container App / Application Insights logs (see docs/sprint_14/decisions.md,
PBI-14-07). Fixed via a strict ALLOWLIST (never `record.__dict__`, per CLAUDE.md §10's "do not
store hidden chain-of-thought" and this PBI's own explicit privacy requirement): only the named
keys in `_ALLOWED_EXTRA_FIELDS` are ever copied from a LogRecord's `extra`-set attributes into
the JSON payload. Every other attribute a caller might pass — accidentally or otherwise,
including any of Authorization/Bearer/API-key/system-prompt/raw-message shape — is silently
excluded, never serialized. Prefer allowlist over denylist (a denylist can only ever exclude
patterns someone already thought of; an allowlist excludes everything by default)."""

import json
import logging
import sys
from contextvars import ContextVar
from typing import Any

correlation_id_ctx_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)

# Structured routing-telemetry fields (PBI-14-07) an approved call site may pass via
# `extra={...}` and have survive JSON serialization. "correlationId"/"correlation_id" are
# deliberately NOT included here: the correlation id in the output always comes from the
# request-scoped `correlation_id_ctx_var` (via CorrelationIdFilter below), never from a
# caller-supplied value — this guarantees a single, tamper-proof correlation id per log line
# regardless of what any individual call site happens to pass.
#
# Naming follows this repo's existing convention for this exact family of fields (camelCase —
# see src.supervisor.orchestrator._routing_diagnostics_payload, apps/api/src/api/routes/chat.py)
# rather than introducing a second, snake_case naming convention for the same concepts.
_ALLOWED_EXTRA_FIELDS: frozenset[str] = frozenset(
    {
        "event",
        "conversationId",
        "messageId",
        "runId",
        "semanticCallAttempted",
        "semanticCallSucceeded",
        "detectedIntent",
        "intentConfidence",
        "alternativeIntents",
        "requiresClarification",
        "routingSource",
        "routingReason",
        "selectedAgent",
        "semanticErrorCategory",
        "durationMs",
    }
)


class CorrelationIdFilter(logging.Filter):
    """Injects the current request's correlation ID into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_ctx_var.get()
        return True


class JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON for structured log ingestion.

    Only `_ALLOWED_EXTRA_FIELDS` keys are read from a LogRecord's `extra`-set attributes — any
    other attribute (standard LogRecord internals, or an unapproved/unexpected field a caller
    passed) is never inspected or serialized. A key is included only when the record actually
    carries it (i.e. some `extra=` dict set it for this specific log call) — an explicit `None`
    value is preserved as JSON `null`; a key no caller ever set is simply absent from the
    output, never coerced to null."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlationId": getattr(record, "correlation_id", None),
        }
        for field_name in _ALLOWED_EXTRA_FIELDS:
            if field_name in record.__dict__:
                payload[field_name] = record.__dict__[field_name]
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(log_level: str = "INFO") -> None:
    """Configure root logging with a structured JSON stdout handler."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(CorrelationIdFilter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level.upper())

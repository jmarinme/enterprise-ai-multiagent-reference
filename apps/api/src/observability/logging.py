"""Structured JSON logging configuration for the API."""

import json
import logging
import sys
from contextvars import ContextVar
from typing import Any

correlation_id_ctx_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


class CorrelationIdFilter(logging.Filter):
    """Injects the current request's correlation ID into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_ctx_var.get()
        return True


class JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON for structured log ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlationId": getattr(record, "correlation_id", None),
        }
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

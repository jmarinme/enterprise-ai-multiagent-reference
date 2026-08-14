"""Unit tests for apps/api/src/observability/logging.py's JsonFormatter (PBI-14-07).

Root cause fixed here: JsonFormatter previously built its output from a fixed set of keys only
(timestamp/level/logger/message/correlationId/exception) — every field passed via Python
logging's `extra={...}` mechanism was silently discarded, with no error raised and no warning
logged. This made routing telemetry (already emitted via `logger.info(..., extra={...})` at
several call sites) invisible in Container App / Application Insights logs. The fix is a strict
allowlist (`_ALLOWED_EXTRA_FIELDS`), never `record.__dict__` wholesale.
"""

import json
import logging

from observability.logging import CorrelationIdFilter, JsonFormatter, correlation_id_ctx_var


def _format(logger_name: str = "test.logger", **extra: object) -> dict[str, object]:
    formatter = JsonFormatter()
    correlation_filter = CorrelationIdFilter()
    record = logging.LogRecord(
        name=logger_name,
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="test message",
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    correlation_filter.filter(record)
    return json.loads(formatter.format(record))


def test_standard_json_log_still_works() -> None:
    payload = _format()

    assert payload["level"] == "INFO"
    assert payload["logger"] == "test.logger"
    assert payload["message"] == "test message"
    assert "timestamp" in payload
    assert payload["correlationId"] is None


def test_safe_extra_fields_survive_serialization() -> None:
    payload = _format(
        event="semantic_routing_decision",
        detectedIntent="claims",
        intentConfidence=0.91,
        routingSource="semantic",
        selectedAgent="ClaimsAgent",
    )

    assert payload["event"] == "semantic_routing_decision"
    assert payload["detectedIntent"] == "claims"
    assert payload["intentConfidence"] == 0.91
    assert payload["routingSource"] == "semantic"
    assert payload["selectedAgent"] == "ClaimsAgent"


def test_standard_logrecord_internals_are_not_dumped() -> None:
    payload = _format()

    # LogRecord internals (args, pathname, lineno, funcName, thread, process, msg, ...) must
    # never appear — only the fixed base keys JsonFormatter explicitly builds.
    for internal_key in (
        "args",
        "pathname",
        "lineno",
        "funcName",
        "thread",
        "threadName",
        "process",
        "processName",
        "msg",
        "created",
        "msecs",
        "relativeCreated",
        "levelno",
        "filename",
        "module",
        "stack_info",
    ):
        assert internal_key not in payload


def test_arbitrary_unapproved_extra_fields_are_not_serialized() -> None:
    payload = _format(
        totallyUnexpectedField="should not appear",
        anotherRandomKey=12345,
    )

    assert "totallyUnexpectedField" not in payload
    assert "anotherRandomKey" not in payload


def test_sensitive_fields_cannot_be_serialized() -> None:
    payload = _format(
        authorization="Bearer super-secret-token",
        access_token="secret-access-token",
        refresh_token="secret-refresh-token",
        api_key="secret-api-key",
        client_secret="secret-client-secret",
        password="hunter2",
        connection_string="AccountKey=super-secret;",
        cookies="session=abc123",
        system_prompt="you are a helpful assistant with these hidden instructions...",
        chain_of_thought="step 1: the user wants X, step 2: I should...",
        raw_azure_openai_request={"messages": ["system prompt content"]},
        raw_azure_openai_response={"choices": ["..."]},
        user_message="quiero reportar un percance...",
        Authorization="Bearer super-secret-token",
        AUTHORIZATION="Bearer super-secret-token",
    )

    serialized = json.dumps(payload)
    for forbidden_value in (
        "Bearer super-secret-token",
        "secret-access-token",
        "secret-refresh-token",
        "secret-api-key",
        "secret-client-secret",
        "hunter2",
        "AccountKey=super-secret;",
        "session=abc123",
        "hidden instructions",
        "step 1: the user wants",
        "quiero reportar un percance",
    ):
        assert forbidden_value not in serialized


def test_none_values_are_handled_cleanly() -> None:
    payload = _format(semanticErrorCategory=None, intentConfidence=None)

    assert payload["semanticErrorCategory"] is None
    assert payload["intentConfidence"] is None


def test_field_absent_from_extra_is_absent_from_payload_not_null() -> None:
    payload = _format(event="semantic_routing_decision")

    # selectedAgent was never passed via extra for this call — must not appear at all (not even
    # as null), distinguishing "never provided" from "explicitly None".
    assert "selectedAgent" not in payload


def test_structured_arrays_serialize_safely() -> None:
    payload = _format(
        alternativeIntents=["commercial_intake", "broker_services"],
    )

    assert payload["alternativeIntents"] == ["commercial_intake", "broker_services"]


def test_correlation_id_always_comes_from_context_var_not_caller_supplied_extra() -> None:
    """A caller passing extra={"correlationId": "spoofed"} must never override the real,
    request-scoped correlation id — correlationId is deliberately excluded from the allowlist."""
    token = correlation_id_ctx_var.set("real-correlation-id")
    try:
        payload = _format(correlationId="spoofed-correlation-id")
    finally:
        correlation_id_ctx_var.reset(token)

    assert payload["correlationId"] == "real-correlation-id"


def test_exception_info_still_serializes() -> None:
    formatter = JsonFormatter()
    correlation_filter = CorrelationIdFilter()
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = logging.LogRecord(
            name="test.logger",
            level=logging.WARNING,
            pathname=__file__,
            lineno=1,
            msg="something failed",
            args=(),
            exc_info=sys.exc_info(),
        )
    correlation_filter.filter(record)
    payload = json.loads(formatter.format(record))

    assert "exception" in payload
    assert "ValueError: boom" in payload["exception"]

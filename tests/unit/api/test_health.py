"""Unit tests for GET /health."""

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_returns_ok_status() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_response_includes_correlation_id_header() -> None:
    response = client.get("/health")

    assert "x-correlation-id" in response.headers


# ---------------------------------------------------------------------------------------------
# GET /ready (Architecture Review Finding A-08): dependency readiness, distinct from /health's
# unconditional liveness signal above.
# ---------------------------------------------------------------------------------------------


def test_ready_returns_ready_when_every_default_dependency_is_healthy() -> None:
    """Default test/local configuration (mock LLM, in-memory conversation store, local
    knowledge provider) has nothing external to check — every check trivially passes."""
    response = client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"] == {
        "llm": "ok",
        "conversationStore": "ok",
        "knowledgeProvider": "ok",
    }


def test_ready_returns_503_and_degraded_when_the_llm_is_unreachable() -> None:
    import api.routes.health as health_module

    class _UnhealthyLLMProvider:
        async def health_check(self) -> bool:
            return False

    original = health_module.get_llm_provider
    health_module.get_llm_provider = lambda: _UnhealthyLLMProvider()  # type: ignore[assignment]
    try:
        response = client.get("/ready")
    finally:
        health_module.get_llm_provider = original

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["llm"] == "unreachable"
    assert body["checks"]["conversationStore"] == "ok"


def test_ready_never_exposes_the_underlying_exception_message() -> None:
    """A failing dependency's exception text (which could contain an endpoint URL, a
    connection string fragment, or other internal detail) must never reach the response body —
    only the fixed word 'unreachable'."""
    import api.routes.health as health_module

    class _ExplodingLLMProvider:
        async def health_check(self) -> bool:
            raise RuntimeError("secret-looking-detail://internal-endpoint:5432/should-not-leak")

    original = health_module.get_llm_provider
    health_module.get_llm_provider = lambda: _ExplodingLLMProvider()  # type: ignore[assignment]
    try:
        response = client.get("/ready")
    finally:
        health_module.get_llm_provider = original

    assert response.status_code == 503
    assert "secret-looking-detail" not in response.text
    assert "internal-endpoint" not in response.text
    assert response.json()["checks"]["llm"] == "unreachable"


def test_ready_response_includes_correlation_id_header() -> None:
    response = client.get("/ready")

    assert "x-correlation-id" in response.headers

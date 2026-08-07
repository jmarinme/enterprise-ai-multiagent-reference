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

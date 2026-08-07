"""Unit tests for correlation ID propagation behavior."""

import uuid

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_generates_correlation_id_when_not_provided() -> None:
    response = client.get("/health")

    correlation_id = response.headers.get("x-correlation-id")
    assert correlation_id is not None
    uuid.UUID(correlation_id)


def test_echoes_client_supplied_correlation_id() -> None:
    supplied = "test-correlation-id-123"

    response = client.get("/health", headers={"X-Correlation-ID": supplied})

    assert response.headers.get("x-correlation-id") == supplied

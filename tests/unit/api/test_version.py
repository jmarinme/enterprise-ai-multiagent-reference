"""Unit tests for GET /version."""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_version_returns_expected_fields() -> None:
    response = client.get("/version")

    assert response.status_code == 200
    body = response.json()
    assert body["name"]
    assert body["version"]
    assert body["environment"]

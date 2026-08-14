"""Unit tests for GET /version."""

from config.settings import Settings, get_settings
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


def test_version_includes_build_traceability_fields() -> None:
    """PBI-14-06: app_version/build_number/commit_sha/component must always be present so a
    deployed image's identity is verifiable from the API response alone."""
    response = client.get("/version")

    assert response.status_code == 200
    body = response.json()
    assert body["app_version"]
    assert body["build_number"]
    assert body["commit_sha"]
    assert body["component"] == "api"


def test_version_build_traceability_fields_are_sourced_from_settings_not_hardcoded() -> None:
    """The pipeline injects real app_version/build_number/commit_sha via env vars consumed by
    Settings — proves the endpoint reflects whatever Settings reports, rather than a literal
    baked into the route handler."""
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_version="99.9.9",
        build_number="12345",
        commit_sha="deadbeefcafe",
    )
    try:
        response = client.get("/version")
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 200
    body = response.json()
    assert body["app_version"] == "99.9.9"
    assert body["build_number"] == "12345"
    assert body["commit_sha"] == "deadbeefcafe"

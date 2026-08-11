"""Unit tests for CORS configuration (PBI-04-02).

Covers: Settings.cors_allowed_origins_list parsing, and the real FastAPI app's CORS behavior
(allowed origin gets Access-Control-Allow-Origin; unlisted origin does not) through TestClient,
proving CORSMiddleware is genuinely wired, not just configured in isolation.
"""

from fastapi.testclient import TestClient
from main import app

from config.settings import Settings

client = TestClient(app)


def test_cors_allowed_origins_list_parses_comma_separated_values() -> None:
    settings = Settings(cors_allowed_origins="https://a.example.com, https://b.example.com")

    assert settings.cors_allowed_origins_list == [
        "https://a.example.com",
        "https://b.example.com",
    ]


def test_cors_allowed_origins_list_drops_empty_entries() -> None:
    settings = Settings(cors_allowed_origins="https://a.example.com,, ")

    assert settings.cors_allowed_origins_list == ["https://a.example.com"]


def test_cors_allowed_origins_default_is_never_a_wildcard() -> None:
    """PBI-04-02 explicit requirement: never "*" for the production-shaped DEV configuration."""
    settings = Settings()

    assert "*" not in settings.cors_allowed_origins_list
    assert settings.cors_allowed_origins_list != []


def test_cors_preflight_allows_the_configured_origin() -> None:
    """The default local dev origin (http://localhost:3000, matching docker-compose's Web
    port) must be allowed for a real CORS preflight against POST /chat."""
    response = client.options(
        "/chat",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_rejects_an_unconfigured_origin() -> None:
    """A real browser request from an origin not in the allow-list must not receive an
    Access-Control-Allow-Origin header — the browser is what actually enforces the block, but
    the middleware must not emit the header for an unlisted origin."""
    response = client.options(
        "/chat",
        headers={
            "Origin": "https://not-the-allowed-web-app.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert "access-control-allow-origin" not in response.headers


def test_cors_actual_get_request_includes_allow_origin_header_for_allowed_origin() -> None:
    """Non-preflight (simple) requests also need the header — GET /health from the allowed
    origin, matching how a real browser fetch() call is actually evaluated."""
    response = client.get("/health", headers={"Origin": "http://localhost:3000"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_preflight_for_conversations_allows_the_authorization_header() -> None:
    """PBI-11-01C regression guard: the exact live failure this fixes — a browser preflight
    for GET /conversations requesting the Authorization header (as the SPA does before every
    Entra ID Bearer-token request, PBI-11-01) must succeed, not 400."""
    response = client.options(
        "/conversations",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed_headers


def test_cors_preflight_for_chat_allows_the_authorization_header() -> None:
    """Same regression guard as above, for POST /chat."""
    response = client.options(
        "/chat",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization, content-type",
        },
    )

    assert response.status_code == 200
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed_headers
    assert "content-type" in allowed_headers


def test_cors_preflight_still_allows_content_type_and_correlation_id() -> None:
    """Preserves the two headers this fix must not regress (PBI-04-02/observability)."""
    response = client.options(
        "/chat",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type, x-correlation-id",
        },
    )

    assert response.status_code == 200
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "content-type" in allowed_headers
    assert "x-correlation-id" in allowed_headers


def test_cors_preflight_for_conversations_rejects_an_unconfigured_origin() -> None:
    """The Authorization-header fix must not loosen origin restriction — an unlisted origin
    still gets no Access-Control-Allow-Origin, even when requesting Authorization."""
    response = client.options(
        "/conversations",
        headers={
            "Origin": "https://not-the-allowed-web-app.example.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert "access-control-allow-origin" not in response.headers

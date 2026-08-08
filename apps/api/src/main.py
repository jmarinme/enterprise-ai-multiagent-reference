"""FastAPI application entrypoint for the TMX API foundation."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.middleware.correlation_id import CORRELATION_ID_HEADER, CorrelationIdMiddleware
from api.routes import chat, conversations, health, version
from config.settings import get_settings
from observability.logging import configure_logging


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.project_name, version=settings.api_version)
    # CORSMiddleware added first (PBI-04-02) so it is the outermost layer — Starlette wraps
    # middleware in the order added, first-added = outermost, matching the standard "CORS
    # should wrap everything, including preflight OPTIONS and error responses" guidance.
    # allow_origins is configuration-driven (Settings.cors_allowed_origins), never "*" — see
    # docs/sprint_04/decisions.md. allow_credentials stays False: this API uses no cookies/
    # session auth, so no credentialed requests exist to allow.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins_list,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", CORRELATION_ID_HEADER],
    )
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(health.router)
    app.include_router(version.router)
    app.include_router(chat.router)
    app.include_router(conversations.router)
    return app


app = create_app()

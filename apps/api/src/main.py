"""FastAPI application entrypoint for the TMX API foundation."""

from fastapi import FastAPI

from api.middleware.correlation_id import CorrelationIdMiddleware
from api.routes import chat, health, version
from config.settings import get_settings
from observability.logging import configure_logging


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.project_name, version=settings.api_version)
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(health.router)
    app.include_router(version.router)
    app.include_router(chat.router)
    return app


app = create_app()

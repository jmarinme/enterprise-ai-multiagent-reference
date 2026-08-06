"""API version endpoint."""

from fastapi import APIRouter, Depends

from config.settings import Settings, get_settings

router = APIRouter(tags=["version"])


@router.get("/version")
async def get_version(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    """Return the API name, version, and running environment."""
    return {
        "name": settings.project_name,
        "version": settings.api_version,
        "environment": settings.environment,
    }

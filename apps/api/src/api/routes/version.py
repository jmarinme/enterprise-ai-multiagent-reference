"""API version endpoint."""

from fastapi import APIRouter, Depends

from config.settings import Settings, get_settings

router = APIRouter(tags=["version"])


@router.get("/version")
async def get_version(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    """Return the API name, version, running environment, and build/deployment traceability
    (PBI-14-06). No secret, credential, or connection-string value is ever included here —
    only the values every deployed image's own metadata already exposes via its registry tag."""
    return {
        "name": settings.project_name,
        "version": settings.api_version,
        "environment": settings.environment,
        "app_version": settings.app_version,
        "build_number": settings.build_number,
        "commit_sha": settings.commit_sha,
        "component": "api",
    }

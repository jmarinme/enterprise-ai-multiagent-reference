"""Liveness health-check endpoint."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def get_health() -> dict[str, str]:
    """Return a simple liveness signal for orchestrators and monitoring."""
    return {"status": "ok"}

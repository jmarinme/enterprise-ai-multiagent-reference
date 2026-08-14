"""Selects an ObservabilityRepository implementation from configuration. Mirrors
src.services.conversation_store.factory exactly, including lazy Cosmos import so the default
in-memory provider never requires azure-cosmos/azure-identity installed or reachable.
"""

from __future__ import annotations

from src.config.settings import ObservabilityStoreSettings
from src.domain.observability_repository import ObservabilityRepository
from src.services.observability_store.in_memory import InMemoryObservabilityRepository


def get_observability_repository(settings: ObservabilityStoreSettings) -> ObservabilityRepository:
    """Return the ObservabilityRepository implementation selected by settings."""
    if settings.observability_store_provider == "in_memory":
        return InMemoryObservabilityRepository()

    if settings.observability_store_provider == "cosmos":
        from src.services.observability_store.cosmos import CosmosObservabilityRepository

        if not settings.cosmos_db_endpoint:
            raise ValueError(
                "COSMOS_DB_ENDPOINT must be set when OBSERVABILITY_STORE_PROVIDER=cosmos"
            )
        return CosmosObservabilityRepository(
            endpoint=settings.cosmos_db_endpoint,
            database_name=settings.cosmos_db_database,
            container_name=settings.observability_runs_container,
        )

    raise ValueError(
        f"Unsupported observability store provider: {settings.observability_store_provider}"
    )

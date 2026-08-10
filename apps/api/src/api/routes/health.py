"""Liveness (/health) and readiness (/ready) endpoints (Architecture Review Finding A-08).

/health stays exactly what it always was: an unconditional liveness signal — "is this process
running" — never touches a downstream dependency, never fails. /ready additionally checks
whether THIS instance can currently serve real traffic: Cosmos DB / Azure OpenAI / Azure AI
Search, but only the ones actually configured (the in-memory/mock/local defaults have nothing
external to check, so they always report ok). Never exposes a connection string, endpoint URL,
API key, or raw exception message — only a per-dependency ok/unreachable word and an overall
status, safe to expose without authentication (matching /health's own existing posture).
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Response

from api.dependencies import (
    get_conversation_repository_dep,
    get_knowledge_retriever,
    get_llm_provider,
)
from src.config.settings import ConversationStoreSettings, KnowledgeSettings

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)

_READINESS_CHECK_TIMEOUT_SECONDS = 5.0
# Reserved, synthetic partition key — never a real userId — so the readiness probe's Cosmos
# query is guaranteed to cost the minimum possible RUs (a partition with no items) without
# needing a second, read-only-vs-readiness-only Cosmos permission model.
_READINESS_PROBE_USER_ID = "__readiness_probe__"


@router.get("/health")
async def get_health() -> dict[str, str]:
    """Return a simple liveness signal for orchestrators and monitoring."""
    return {"status": "ok"}


async def _check_llm() -> bool:
    try:
        async with asyncio.timeout(_READINESS_CHECK_TIMEOUT_SECONDS):
            return await get_llm_provider().health_check()
    except Exception:  # noqa: BLE001 -- a readiness check must never itself raise/crash the endpoint; any failure (network, auth, timeout, a provider bug) is deliberately reported as "unreachable", not propagated.
        logger.warning("readiness_check_failed", extra={"dependency": "llm"})
        return False


async def _check_conversation_store() -> bool:
    if ConversationStoreSettings().conversation_store_provider != "cosmos":
        return True  # in-memory default: no external dependency to check
    try:
        async with asyncio.timeout(_READINESS_CHECK_TIMEOUT_SECONDS):
            await get_conversation_repository_dep().list_conversations(_READINESS_PROBE_USER_ID)
        return True
    except Exception:  # noqa: BLE001 -- a readiness check must never itself raise/crash the endpoint; any failure (network, auth, timeout, a provider bug) is deliberately reported as "unreachable", not propagated.
        logger.warning("readiness_check_failed", extra={"dependency": "conversation_store"})
        return False


async def _check_knowledge_provider() -> bool:
    if KnowledgeSettings().knowledge_provider != "azure_ai_search":
        return True  # local default: no external dependency to check
    try:
        from src.rag.models import KnowledgeQuery

        async with asyncio.timeout(_READINESS_CHECK_TIMEOUT_SECONDS):
            await get_knowledge_retriever().retrieve(
                KnowledgeQuery(text="readiness probe", top_k=1)
            )
        return True
    except Exception:  # noqa: BLE001 -- a readiness check must never itself raise/crash the endpoint; any failure (network, auth, timeout, a provider bug) is deliberately reported as "unreachable", not propagated.
        logger.warning("readiness_check_failed", extra={"dependency": "knowledge_provider"})
        return False


@router.get("/ready")
async def get_ready(response: Response) -> dict[str, object]:
    """Dependency readiness. Returns HTTP 200 with `status: "ready"` when every *configured*
    dependency is reachable, or HTTP 503 with `status: "degraded"` and the specific
    dependency/dependencies at fault otherwise — so Container Apps' own readiness probe (and
    any future load balancer) correctly stops routing traffic to a degraded instance instead of
    relying solely on /health, which cannot see this (Finding A-08's exact gap)."""
    llm_ok, conversation_store_ok, knowledge_ok = await asyncio.gather(
        _check_llm(), _check_conversation_store(), _check_knowledge_provider()
    )
    checks = {
        "llm": "ok" if llm_ok else "unreachable",
        "conversationStore": "ok" if conversation_store_ok else "unreachable",
        "knowledgeProvider": "ok" if knowledge_ok else "unreachable",
    }
    all_ok = llm_ok and conversation_store_ok and knowledge_ok
    response.status_code = 200 if all_ok else 503
    return {"status": "ready" if all_ok else "degraded", "checks": checks}

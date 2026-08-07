"""Supervisor Protocol — the public contract for the platform's orchestration entry point.

SupervisorOrchestrator (orchestrator.py) is the current, and so far only, implementation.
Callers (e.g. apps/api's POST /chat route) should depend on this Protocol, not on
SupervisorOrchestrator directly, so an alternative implementation could be substituted without
changing callers.
"""

from __future__ import annotations

from typing import Protocol

from src.supervisor.models import AgentRequest, AgentResponse


class Supervisor(Protocol):
    """Contract for the platform's single conversational orchestration entry point."""

    async def handle(self, request: AgentRequest) -> AgentResponse: ...

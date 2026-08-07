"""Typed exceptions for the Supervisor orchestration pipeline."""

from __future__ import annotations

from src.supervisor.models import IntentCategory


class SupervisorError(Exception):
    """Base class for all Supervisor orchestration errors."""


class AgentNotFoundError(SupervisorError):
    """Raised when the AgentRegistry has no Agent registered for a resolved intent."""

    def __init__(self, intent: IntentCategory) -> None:
        self.intent = intent
        super().__init__(f"No agent registered for intent '{intent.value}'")

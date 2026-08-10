"""ClaimsWorkflowProvider — the location-transparent seam for the Claims post-confirmation
transaction. See src.core.workflow_provider (package docstring) for the full contract.
"""

from __future__ import annotations

from typing import Protocol

from src.core.workflow_provider.models import ClaimsWorkflowInput, ClaimsWorkflowResult


class ClaimsWorkflowProvider(Protocol):
    """Contract every Claims workflow execution backend implements. Never raises to its
    caller — every failure mode is normalized into ClaimsWorkflowResult(success=False,
    error=...)."""

    async def run(self, workflow_input: ClaimsWorkflowInput) -> ClaimsWorkflowResult: ...

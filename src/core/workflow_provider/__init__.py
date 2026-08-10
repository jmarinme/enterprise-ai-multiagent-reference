"""WorkflowProvider framework (PBI-06-01): the location-transparent seam between ClaimsAgent's
conversational state machine and wherever the post-confirmation claims transaction (policy
re-check, payment validation, coverage validation, claim registration, adjuster assignment)
actually executes — in-process, or a Durable Functions orchestration. Resolves Architecture
Review Finding A-03 / ADR-0003.

ClaimsAgent (src.agents.claims.workflow) still owns 100% of the conversation: field collection,
extraction, confirmation. A WorkflowProvider is invoked exactly once, only after the caller has
confirmed, and only to carry out the deterministic multi-step transaction — it never holds
conversational state.
"""

from __future__ import annotations

from src.core.workflow_provider.models import ClaimsWorkflowInput, ClaimsWorkflowResult
from src.core.workflow_provider.protocol import ClaimsWorkflowProvider

__all__ = ["ClaimsWorkflowInput", "ClaimsWorkflowProvider", "ClaimsWorkflowResult"]

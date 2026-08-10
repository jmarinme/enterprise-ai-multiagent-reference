"""InProcessClaimsWorkflowProvider — the default WorkflowProvider backend
(CLAIMS_WORKFLOW_PROVIDER=inprocess). Runs claim registration followed by adjuster assignment as
plain in-process async Tool calls through a ToolProvider — the same two Tool calls
src.agents.claims.workflow._handle_ready_to_register/_handle_registered already make, only
relocated behind the ClaimsWorkflowProvider seam so the caller (advance_claims_intake) does not
need to know which backend executed them.
"""

from __future__ import annotations

from src.core.tool_provider.protocol import ToolProvider
from src.core.workflow_provider.models import ClaimsWorkflowInput, ClaimsWorkflowResult
from src.tools.models import ToolRequest


class InProcessClaimsWorkflowProvider:
    """ClaimsWorkflowProvider backend that runs claim registration + adjuster assignment
    in-process, through an injected ToolProvider."""

    def __init__(self, tool_provider: ToolProvider) -> None:
        self._tool_provider = tool_provider

    async def run(self, workflow_input: ClaimsWorkflowInput) -> ClaimsWorkflowResult:
        ctx = {
            "correlation_id": workflow_input.correlation_id,
            "conversation_id": workflow_input.conversation_id,
            "user_id": workflow_input.user_id,
        }

        registration = await self._tool_provider.execute(
            ToolRequest(
                tool_name="claim_registration",
                tool_input={
                    "policy_number": workflow_input.policy_number,
                    "event_date": workflow_input.event_date,
                    "event_time": workflow_input.event_time,
                    "event_location": workflow_input.event_location,
                    "loss_type": workflow_input.loss_type,
                    "loss_description": workflow_input.loss_description,
                    "contact_name": workflow_input.contact_name,
                    "contact_phone": workflow_input.contact_phone,
                    "contact_email": workflow_input.contact_email,
                    "injuries_reported": workflow_input.injuries_reported,
                    "third_parties_involved": workflow_input.third_parties_involved,
                },
                **ctx,
            )
        )
        if not registration.success or registration.data is None:
            return ClaimsWorkflowResult(success=False, error=registration.error)

        claim_reference = registration.data.claim_reference

        assignment = await self._tool_provider.execute(
            ToolRequest(
                tool_name="adjuster_assignment",
                tool_input={"claim_reference": claim_reference},
                **ctx,
            )
        )
        adjuster_name = (
            assignment.data.adjuster_name if assignment.success and assignment.data else None
        )
        return ClaimsWorkflowResult(
            success=True, claim_reference=claim_reference, adjuster_name=adjuster_name
        )

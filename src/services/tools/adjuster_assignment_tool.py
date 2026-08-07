"""Synthetic AdjusterAssignmentTool — assigns a synthetic adjuster to an already-registered
claim. No real adjuster roster, no Azure calls, no external APIs. Assignment only; it never
determines coverage or claim outcome.
"""

from __future__ import annotations

from pydantic import BaseModel

from src.services.tools.synthetic.provider import SYNTHETIC_ADJUSTERS, SyntheticAdjusterRecord
from src.tools.models import ToolExecutionContext, ToolResult


class AdjusterAssignmentInput(BaseModel):
    claim_reference: str


class AdjusterAssignmentTool:
    """Deterministically assigns a synthetic adjuster to a claim reference.

    The same claim_reference always resolves to the same adjuster (assignment is a pure
    function of the reference string, not randomness or wall-clock state), so retries after a
    transient failure are idempotent.
    """

    name = "adjuster_assignment"
    description = "Assigns a synthetic adjuster to an already-registered synthetic claim."
    version = "1.0.0"
    input_model = AdjusterAssignmentInput

    async def execute(
        self, tool_input: AdjusterAssignmentInput, context: ToolExecutionContext
    ) -> ToolResult[SyntheticAdjusterRecord]:
        if not tool_input.claim_reference.strip():
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="A claim_reference is required to assign an adjuster",
                correlation_id=context.correlation_id,
            )
        index = sum(ord(char) for char in tool_input.claim_reference) % len(SYNTHETIC_ADJUSTERS)
        return ToolResult(
            tool_name=self.name,
            success=True,
            data=SYNTHETIC_ADJUSTERS[index],
            correlation_id=context.correlation_id,
        )

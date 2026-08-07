"""Synthetic ClaimsStatusTool — deterministic, synthetic data only. No real claims system,
no Azure calls, no external APIs.
"""

from __future__ import annotations

from pydantic import BaseModel

from src.services.tools.synthetic.provider import SYNTHETIC_CLAIMS, SyntheticClaimRecord
from src.tools.models import ToolExecutionContext, ToolResult


class ClaimsStatusInput(BaseModel):
    claim_number: str


class ClaimsStatusTool:
    """Looks up a synthetic claim record by claim number."""

    name = "claims_status"
    description = "Looks up a synthetic claim's status by claim number."
    version = "1.0.0"
    input_model = ClaimsStatusInput

    async def execute(
        self, tool_input: ClaimsStatusInput, context: ToolExecutionContext
    ) -> ToolResult[SyntheticClaimRecord]:
        record = SYNTHETIC_CLAIMS.get(tool_input.claim_number)
        if record is None:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"No synthetic claim found for '{tool_input.claim_number}'",
                correlation_id=context.correlation_id,
            )
        return ToolResult(
            tool_name=self.name,
            success=True,
            data=record,
            correlation_id=context.correlation_id,
        )

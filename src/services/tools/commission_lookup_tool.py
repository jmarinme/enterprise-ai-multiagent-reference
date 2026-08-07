"""Synthetic CommissionLookupTool — deterministic, synthetic data only. No real commission
system, no Azure calls, no external APIs.
"""

from __future__ import annotations

from pydantic import BaseModel

from src.services.tools.synthetic.provider import SYNTHETIC_COMMISSIONS, SyntheticCommissionRecord
from src.tools.models import ToolExecutionContext, ToolResult


class CommissionLookupInput(BaseModel):
    broker_id: str
    commission_period: str


class CommissionLookupTool:
    """Looks up a synthetic broker's commission for a given period."""

    name = "commission_lookup"
    description = "Looks up a synthetic broker's commission amount and status for a period."
    version = "1.0.0"
    input_model = CommissionLookupInput

    async def execute(
        self, tool_input: CommissionLookupInput, context: ToolExecutionContext
    ) -> ToolResult[SyntheticCommissionRecord]:
        record = SYNTHETIC_COMMISSIONS.get((tool_input.broker_id, tool_input.commission_period))
        if record is None:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=(
                    f"No synthetic commission found for broker '{tool_input.broker_id}' in "
                    f"period '{tool_input.commission_period}'"
                ),
                correlation_id=context.correlation_id,
            )
        return ToolResult(
            tool_name=self.name,
            success=True,
            data=record,
            correlation_id=context.correlation_id,
        )

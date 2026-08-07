"""Synthetic PaymentStatusTool — deterministic, synthetic data only. No real payment system,
no Azure calls, no external APIs.
"""

from __future__ import annotations

from pydantic import BaseModel

from src.services.tools.synthetic.provider import (
    SYNTHETIC_PAYMENT_STATUSES,
    SyntheticPaymentStatusRecord,
)
from src.tools.models import ToolExecutionContext, ToolResult


class PaymentStatusInput(BaseModel):
    policy_number: str


class PaymentStatusTool:
    """Looks up a synthetic policy's payment status by policy number."""

    name = "payment_status"
    description = "Looks up whether a synthetic policy's payments are current."
    version = "1.0.0"
    input_model = PaymentStatusInput

    async def execute(
        self, tool_input: PaymentStatusInput, context: ToolExecutionContext
    ) -> ToolResult[SyntheticPaymentStatusRecord]:
        record = SYNTHETIC_PAYMENT_STATUSES.get(tool_input.policy_number)
        if record is None:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"No synthetic payment status found for '{tool_input.policy_number}'",
                correlation_id=context.correlation_id,
            )
        return ToolResult(
            tool_name=self.name,
            success=True,
            data=record,
            correlation_id=context.correlation_id,
        )

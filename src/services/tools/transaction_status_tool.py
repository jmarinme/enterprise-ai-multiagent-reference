"""Synthetic TransactionStatusTool — deterministic, synthetic data only. No real transaction
system, no Azure calls, no external APIs.
"""

from __future__ import annotations

from pydantic import BaseModel

from src.services.tools.synthetic.provider import SYNTHETIC_TRANSACTIONS, SyntheticTransactionRecord
from src.tools.models import ToolExecutionContext, ToolResult


class TransactionStatusInput(BaseModel):
    transaction_reference: str


class TransactionStatusTool:
    """Looks up a synthetic transaction/request record by transaction reference."""

    name = "transaction_status"
    description = "Looks up a synthetic insurance transaction/request's status by reference."
    version = "1.0.0"
    input_model = TransactionStatusInput

    async def execute(
        self, tool_input: TransactionStatusInput, context: ToolExecutionContext
    ) -> ToolResult[SyntheticTransactionRecord]:
        record = SYNTHETIC_TRANSACTIONS.get(tool_input.transaction_reference)
        if record is None:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"No synthetic transaction found for '{tool_input.transaction_reference}'",
                correlation_id=context.correlation_id,
            )
        return ToolResult(
            tool_name=self.name,
            success=True,
            data=record,
            correlation_id=context.correlation_id,
        )

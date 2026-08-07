"""Synthetic BrokerAccountLookupTool — deterministic, synthetic data only. No real broker
system, no Azure calls, no external APIs.
"""

from __future__ import annotations

from pydantic import BaseModel

from src.services.tools.synthetic.provider import SYNTHETIC_BROKERS, SyntheticBrokerRecord
from src.tools.models import ToolExecutionContext, ToolResult


class BrokerAccountLookupInput(BaseModel):
    broker_id: str


class BrokerAccountLookupTool:
    """Looks up a synthetic broker account record by broker id."""

    name = "broker_account_lookup"
    description = "Looks up a synthetic broker account by broker id."
    version = "1.0.0"
    input_model = BrokerAccountLookupInput

    async def execute(
        self, tool_input: BrokerAccountLookupInput, context: ToolExecutionContext
    ) -> ToolResult[SyntheticBrokerRecord]:
        record = SYNTHETIC_BROKERS.get(tool_input.broker_id)
        if record is None:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"No synthetic broker account found for '{tool_input.broker_id}'",
                correlation_id=context.correlation_id,
            )
        return ToolResult(
            tool_name=self.name,
            success=True,
            data=record,
            correlation_id=context.correlation_id,
        )

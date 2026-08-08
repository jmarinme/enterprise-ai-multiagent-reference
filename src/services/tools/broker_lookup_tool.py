"""Synthetic BrokerLookupTool (PBI-05-01) — deterministic, synthetic data only. No real broker
directory, no Azure calls, no external APIs. Structurally implements src.tools.protocol.Tool
(Protocols are structural, no explicit inheritance needed).

Mirrors CustomerLookupTool's shape exactly: searches SYNTHETIC_BROKERS by a case-insensitive,
partial name match, so a caller ("soy Synthetic Brokerage One", "mi correduría es Synthetic
Brokerage Two") never needs to know or type an internal broker_id — regardless of which legacy
ID prefix (BRK-SYN-*, SYN-BRK-*) that broker happens to use (see
src.services.tools.synthetic.provider's module docstring for the namespace history).
"""

from __future__ import annotations

from pydantic import BaseModel

from src.services.tools.synthetic.provider import SYNTHETIC_BROKERS, SyntheticBrokerRecord
from src.tools.models import ToolExecutionContext, ToolResult


class BrokerLookupInput(BaseModel):
    full_name: str


class BrokerSearchResult(BaseModel):
    matches: list[SyntheticBrokerRecord]


class BrokerLookupTool:
    """Searches the synthetic broker directory by (case-insensitive, partial) name."""

    name = "broker_lookup"
    description = "Searches for a synthetic broker by name and returns matching accounts."
    version = "1.0.0"
    input_model = BrokerLookupInput

    async def execute(
        self, tool_input: BrokerLookupInput, context: ToolExecutionContext
    ) -> ToolResult[BrokerSearchResult]:
        query = tool_input.full_name.strip().lower()
        matches = [
            record
            for record in SYNTHETIC_BROKERS.values()
            if query and query in record.broker_name.lower()
        ]

        if not matches:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"No synthetic broker found matching '{tool_input.full_name}'",
                correlation_id=context.correlation_id,
            )
        return ToolResult(
            tool_name=self.name,
            success=True,
            data=BrokerSearchResult(matches=matches),
            correlation_id=context.correlation_id,
        )

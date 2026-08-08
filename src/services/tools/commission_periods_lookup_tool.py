"""Synthetic CommissionPeriodsLookupTool (PBI-05-01) — deterministic, synthetic data only. No
real commission system, no Azure calls, no external APIs.

Used only when a commission_lookup for a specific period comes back empty, so BrokerAgent can
explain the miss naturally and name the periods that *do* have data ("Solo tengo datos para
2026-Q1 y 2026-Q2") instead of a bare "not found" — CLAUDE.md §2's "never invent a business
fact" cuts both ways: the Agent must not invent available periods either, so this is a real
Tool call, not a hardcoded list.
"""

from __future__ import annotations

from pydantic import BaseModel

from src.services.tools.synthetic.provider import SYNTHETIC_COMMISSIONS
from src.tools.models import ToolExecutionContext, ToolResult


class CommissionPeriodsLookupInput(BaseModel):
    broker_id: str


class CommissionPeriodsResult(BaseModel):
    periods: list[str]


class CommissionPeriodsLookupTool:
    """Lists every commission period on file for a given broker_id (possibly empty)."""

    name = "commission_periods_lookup"
    description = "Lists the commission periods with data on file for a synthetic broker."
    version = "1.0.0"
    input_model = CommissionPeriodsLookupInput

    async def execute(
        self, tool_input: CommissionPeriodsLookupInput, context: ToolExecutionContext
    ) -> ToolResult[CommissionPeriodsResult]:
        periods = sorted(
            period
            for (broker_id, period) in SYNTHETIC_COMMISSIONS
            if broker_id == tool_input.broker_id
        )
        return ToolResult(
            tool_name=self.name,
            success=True,
            data=CommissionPeriodsResult(periods=periods),
            correlation_id=context.correlation_id,
        )

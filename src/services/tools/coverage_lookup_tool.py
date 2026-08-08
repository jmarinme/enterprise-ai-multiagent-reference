"""Synthetic CoverageLookupTool (PBI-04-04) — deterministic, synthetic data only. No real
policy administration system, no Azure calls, no external APIs. Structurally implements
src.tools.protocol.Tool (Protocols are structural, no explicit inheritance needed).

Used by ClaimsAgent's business-validation step to report a policy's coverage type, limit, and
deductible as a fact — CLAUDE.md §2 forbids this Agent from ever determining final coverage or
adjudicating a claim; this Tool only surfaces what is on file, exactly like PolicyLookupTool/
PaymentStatusTool already do for status/payment facts.
"""

from __future__ import annotations

from pydantic import BaseModel

from src.services.tools.synthetic.provider import SYNTHETIC_COVERAGES, SyntheticCoverageRecord
from src.tools.models import ToolExecutionContext, ToolResult


class CoverageLookupInput(BaseModel):
    policy_number: str


class CoverageLookupTool:
    """Looks up a synthetic policy's coverage record by policy number."""

    name = "coverage_lookup"
    description = "Looks up a synthetic policy's coverage type, limit, and deductible."
    version = "1.0.0"
    input_model = CoverageLookupInput

    async def execute(
        self, tool_input: CoverageLookupInput, context: ToolExecutionContext
    ) -> ToolResult[SyntheticCoverageRecord]:
        record = SYNTHETIC_COVERAGES.get(tool_input.policy_number)
        if record is None:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"No synthetic coverage record found for '{tool_input.policy_number}'",
                correlation_id=context.correlation_id,
            )
        return ToolResult(
            tool_name=self.name,
            success=True,
            data=record,
            correlation_id=context.correlation_id,
        )

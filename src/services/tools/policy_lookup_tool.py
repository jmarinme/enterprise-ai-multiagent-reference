"""Synthetic PolicyLookupTool — deterministic, synthetic data only. No real policy system,
no Azure calls, no external APIs. Structurally implements src.tools.protocol.Tool (Protocols
are structural, no explicit inheritance needed).
"""

from __future__ import annotations

from pydantic import BaseModel

from src.services.tools.synthetic.provider import SYNTHETIC_POLICIES, SyntheticPolicyRecord
from src.tools.models import ToolExecutionContext, ToolResult


class PolicyLookupInput(BaseModel):
    policy_number: str


class PolicyLookupTool:
    """Looks up a synthetic policy record by policy number."""

    name = "policy_lookup"
    description = "Looks up a synthetic policy record by policy number."
    version = "1.0.0"
    input_model = PolicyLookupInput

    async def execute(
        self, tool_input: PolicyLookupInput, context: ToolExecutionContext
    ) -> ToolResult[SyntheticPolicyRecord]:
        record = SYNTHETIC_POLICIES.get(tool_input.policy_number)
        if record is None:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"No synthetic policy found for '{tool_input.policy_number}'",
                correlation_id=context.correlation_id,
            )
        return ToolResult(
            tool_name=self.name,
            success=True,
            data=record,
            correlation_id=context.correlation_id,
        )

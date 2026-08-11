"""Synthetic CustomerLookupTool (PBI-04-04) — deterministic, synthetic data only. No real
customer system, no Azure calls, no external APIs. Structurally implements
src.tools.protocol.Tool (Protocols are structural, no explicit inheritance needed).

Supports the "customer discovery" conversational flow: instead of immediately requiring a
policy number, ClaimsAgent asks the caller's name first, searches this synthetic customer
directory, and returns every matching customer's policies so the caller can be guided to pick
the right one — never a business fact by itself, always resolved back through PolicyLookupTool/
CoverageLookupTool once a single policy is selected.
"""

from __future__ import annotations

from pydantic import BaseModel

from src.common.text_normalization import normalize_for_search
from src.services.tools.synthetic.provider import SYNTHETIC_CUSTOMERS, SYNTHETIC_POLICIES
from src.tools.models import ToolExecutionContext, ToolResult


class CustomerLookupInput(BaseModel):
    full_name: str


class CustomerPolicySummary(BaseModel):
    policy_number: str
    line_of_business: str
    vehicle_description: str | None = None


class CustomerMatch(BaseModel):
    customer_id: str
    full_name: str
    policies: list[CustomerPolicySummary]


class CustomerSearchResult(BaseModel):
    matches: list[CustomerMatch]


class CustomerLookupTool:
    """Searches the synthetic customer directory by (case-insensitive, partial) full name."""

    name = "customer_lookup"
    description = "Searches for a synthetic customer by full name and returns their policies."
    version = "1.0.0"
    input_model = CustomerLookupInput

    async def execute(
        self, tool_input: CustomerLookupInput, context: ToolExecutionContext
    ) -> ToolResult[CustomerSearchResult]:
        # PBI-09-01 final validation: accent-insensitive ("Juan Perez" must still find "Juan
        # Pérez") — a live conversational test surfaced this as a real, common-case defect.
        query = normalize_for_search(tool_input.full_name.strip())
        matches = [
            CustomerMatch(
                customer_id=record.customer_id,
                full_name=record.full_name,
                policies=[
                    CustomerPolicySummary(
                        policy_number=policy.policy_number,
                        line_of_business=policy.line_of_business,
                        vehicle_description=policy.vehicle_description,
                    )
                    for policy_number in record.policy_numbers
                    if (policy := SYNTHETIC_POLICIES.get(policy_number)) is not None
                ],
            )
            for record in SYNTHETIC_CUSTOMERS.values()
            if query and query in normalize_for_search(record.full_name)
        ]

        if not matches:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"No synthetic customer found matching '{tool_input.full_name}'",
                correlation_id=context.correlation_id,
            )
        return ToolResult(
            tool_name=self.name,
            success=True,
            data=CustomerSearchResult(matches=matches),
            correlation_id=context.correlation_id,
        )

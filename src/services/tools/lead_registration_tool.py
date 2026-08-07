"""Synthetic LeadRegistrationTool — registers a synthetic commercial-intake lead and generates
a synthetic lead reference. No real CRM/lead system, no Azure calls, no external APIs, and no
quoting/underwriting/acceptance logic: registration only records the reported facts, it never
quotes, underwrites, or guarantees acceptance (CLAUDE.md §2, Commercial Intake Agent permitted
scope).

Mirrors src.services.tools.claim_registration_tool.ClaimRegistrationTool's shape (sequential
synthetic reference generation, stateless otherwise). Not unified into a shared base with
ClaimRegistrationTool/CommissionPaymentRequestTool despite the now-three-times-repeated
counter+reference-format pattern — each Tool's output record has different field names, so a
generic base would need more machinery than the few duplicated lines it would save; see
docs/sprint_01/decisions.md.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel

from src.tools.models import ToolExecutionContext, ToolResult


class LeadRegistrationInput(BaseModel):
    company_name: str
    contact_name: str
    preferred_contact_channel: str
    insurance_need: str
    risk_description: str
    contact_email: str | None = None
    contact_phone: str | None = None


class SyntheticLeadRegistrationRecord(BaseModel):
    lead_reference: str
    registered_at: str


class LeadRegistrationTool:
    """Registers a synthetic commercial-intake lead and returns a generated reference."""

    name = "lead_registration"
    description = "Registers a synthetic commercial-intake lead and generates a lead reference."
    version = "1.0.0"
    input_model = LeadRegistrationInput

    def __init__(self) -> None:
        self._sequence = 0

    async def execute(
        self, tool_input: LeadRegistrationInput, context: ToolExecutionContext
    ) -> ToolResult[SyntheticLeadRegistrationRecord]:
        self._sequence += 1
        now = datetime.now(UTC)
        lead_reference = f"SYN-LEAD-{now.year}-{self._sequence:04d}"
        return ToolResult(
            tool_name=self.name,
            success=True,
            data=SyntheticLeadRegistrationRecord(
                lead_reference=lead_reference,
                registered_at=now.isoformat(),
            ),
            correlation_id=context.correlation_id,
        )

"""Synthetic CommissionPaymentRequestTool — registers a synthetic commission-payment request
and generates a synthetic reference. No real payment system, no Azure calls, no external APIs,
and no financial execution: this only records that a payment was requested, it never approves,
executes, or transfers a real payment (CLAUDE.md §2, Broker Services Agent permitted scope).

Mirrors src.services.tools.claim_registration_tool.ClaimRegistrationTool's shape (sequential
synthetic reference generation). Eligibility (is this commission actually payable right now?)
is a business-timing decision made by the Broker Agent's workflow before calling this Tool —
this Tool itself is a stateless-per-call registrar, consistent with ClaimRegistrationTool's own
precedent of not duplicating the lookup/eligibility check the Agent already performed.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel

from src.tools.models import ToolExecutionContext, ToolResult


class CommissionPaymentRequestInput(BaseModel):
    broker_id: str
    commission_period: str


class SyntheticCommissionPaymentRequestRecord(BaseModel):
    payment_request_reference: str
    requested_at: str


class CommissionPaymentRequestTool:
    """Registers a synthetic commission-payment request and returns a generated reference."""

    name = "commission_payment_request"
    description = "Registers a synthetic commission-payment request and generates a reference."
    version = "1.0.0"
    input_model = CommissionPaymentRequestInput

    def __init__(self) -> None:
        self._sequence = 0

    async def execute(
        self, tool_input: CommissionPaymentRequestInput, context: ToolExecutionContext
    ) -> ToolResult[SyntheticCommissionPaymentRequestRecord]:
        self._sequence += 1
        now = datetime.now(UTC)
        reference = f"SYN-PAYREQ-{now.year}-{self._sequence:04d}"
        return ToolResult(
            tool_name=self.name,
            success=True,
            data=SyntheticCommissionPaymentRequestRecord(
                payment_request_reference=reference,
                requested_at=now.isoformat(),
            ),
            correlation_id=context.correlation_id,
        )

"""Synthetic ClaimRegistrationTool — registers a synthetic claim notice and generates a
synthetic claim reference. No real claims system, no Azure calls, no external APIs, and no
coverage/adjudication logic: registration only records the reported facts, it never approves,
rejects, or evaluates coverage (CLAUDE.md §2, Claims Agent permitted scope).
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel

from src.tools.models import ToolExecutionContext, ToolResult


class ClaimRegistrationInput(BaseModel):
    policy_number: str
    event_date: str
    event_location: str
    loss_type: str
    loss_description: str
    contact_name: str
    contact_phone: str
    event_time: str | None = None
    contact_email: str | None = None
    injuries_reported: bool = False
    third_parties_involved: bool = False


class SyntheticClaimRegistrationRecord(BaseModel):
    claim_reference: str
    registered_at: str


class ClaimRegistrationTool:
    """Registers a synthetic claim notice and returns a generated reference.

    Holds a per-instance sequence counter, mirroring a real claims system issuing sequential
    reference numbers — deterministic within a single running process, reset per test/process,
    never derived from randomness.
    """

    name = "claim_registration"
    description = "Registers a synthetic claim notice and generates a synthetic claim reference."
    version = "1.0.0"
    input_model = ClaimRegistrationInput

    def __init__(self) -> None:
        self._sequence = 0

    async def execute(
        self, tool_input: ClaimRegistrationInput, context: ToolExecutionContext
    ) -> ToolResult[SyntheticClaimRegistrationRecord]:
        self._sequence += 1
        now = datetime.now(UTC)
        claim_reference = f"SYN-CLM-{now.year}-{self._sequence:04d}"
        return ToolResult(
            tool_name=self.name,
            success=True,
            data=SyntheticClaimRegistrationRecord(
                claim_reference=claim_reference,
                registered_at=now.isoformat(),
            ),
            correlation_id=context.correlation_id,
        )

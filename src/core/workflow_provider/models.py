"""Typed input/output for the Claims post-confirmation workflow — the same fields
src.agents.claims.workflow._handle_ready_to_register already sends to the claim_registration
Tool, plus what _handle_registered needs for adjuster assignment. Deliberately flat and Tool-
shaped, not a copy of ClaimsIntakeState: a WorkflowProvider only ever sees the fields it needs
to carry out the transaction, never the conversational bookkeeping fields (candidates,
last_asked_field, opening_acknowledged, ...).
"""

from __future__ import annotations

from pydantic import BaseModel


class ClaimsWorkflowInput(BaseModel):
    """Everything a Claims workflow run needs, once a caller has confirmed."""

    correlation_id: str | None = None
    conversation_id: str | None = None
    user_id: str | None = None

    policy_number: str
    event_date: str | None = None
    event_time: str | None = None
    event_location: str | None = None
    loss_type: str | None = None
    loss_description: str | None = None
    contact_name: str
    contact_phone: str | None = None
    contact_email: str | None = None
    injuries_reported: bool = False
    third_parties_involved: bool = False


class ClaimsWorkflowResult(BaseModel):
    """Outcome of a Claims workflow run. adjuster_name is None when registration succeeded but
    assignment is still pending — the same "adjuster_pending" outcome the in-process handler
    chain already surfaces, never a failure by itself."""

    success: bool
    claim_reference: str | None = None
    adjuster_name: str | None = None
    error: str | None = None

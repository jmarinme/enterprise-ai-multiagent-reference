"""Unit tests for the claims-intake state machine (advance_claims_intake): the dict-dispatched
per-status handlers, driven end-to-end through real synthetic Tools via ToolExecutor. Covers
the four required synthetic policy scenarios, the not-found retry path, and duplicate
registration prevention.
"""

import re

from src.agents.claims.state import ClaimsIntakeState, ClaimsIntakeStatus
from src.agents.claims.workflow import advance_claims_intake
from src.services.tools.adjuster_assignment_tool import AdjusterAssignmentTool
from src.services.tools.claim_registration_tool import ClaimRegistrationTool
from src.services.tools.payment_status_tool import PaymentStatusTool
from src.services.tools.policy_lookup_tool import PolicyLookupTool
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry

_CLAIM_REFERENCE_PATTERN = re.compile(r"^SYN-CLM-\d{4}-\d{4}$")


def _build_executor() -> ToolExecutor:
    registry = InMemoryToolRegistry()
    registry.register(PolicyLookupTool())
    registry.register(PaymentStatusTool())
    registry.register(ClaimRegistrationTool())
    registry.register(AdjusterAssignmentTool())
    return ToolExecutor(tool_registry=registry)


def _ready_state(policy_number: str) -> ClaimsIntakeState:
    return ClaimsIntakeState(
        status=ClaimsIntakeStatus.VALIDATING_POLICY,
        policy_number=policy_number,
        event_date="2026-08-01",
        event_location="Main St",
        loss_type="collision",
        loss_description="Rear-ended at a stoplight.",
        contact_name="Jane Caller",
        contact_phone="555-123-4567",
        injuries_reported=False,
        third_parties_involved=True,
    )


async def test_new_conversation_asks_for_the_first_missing_field() -> None:
    state, notices = await advance_claims_intake(
        ClaimsIntakeState(), "I need to file a claim", _build_executor()
    )

    assert state.status == ClaimsIntakeStatus.COLLECTING_INFORMATION
    assert state.last_asked_field == "policy_number"
    assert len(notices) == 1


async def test_full_multi_turn_conversation_registers_and_assigns_an_adjuster() -> None:
    executor = _build_executor()
    state = ClaimsIntakeState()
    turns = [
        "I need to file a claim",
        "SYN-POL-0001",
        "2026-08-01",
        "In my driveway",
        "It was a collision",
        "Another car hit me while parked",
        "Jane Caller",
        "555-123-4567",
        "no",
        "yes",
    ]

    all_notices: list[str] = []
    for message in turns:
        state, notices = await advance_claims_intake(state, message, executor)
        all_notices.append(" ".join(notices))

    assert state.status == ClaimsIntakeStatus.ADJUSTER_ASSIGNED
    assert state.claim_reference is not None
    assert _CLAIM_REFERENCE_PATTERN.match(state.claim_reference)
    assert state.adjuster_assigned is not None
    assert "active" in all_notices[-1].lower()
    assert "claim reference is" in all_notices[-1].lower()
    assert "assigned" in all_notices[-1].lower()


async def test_active_policy_with_payment_issue_does_not_block_registration() -> None:
    state, notices = await advance_claims_intake(
        _ready_state("SYN-POL-0002"), "confirmed", _build_executor()
    )

    combined = " ".join(notices).lower()
    assert "payment issue" in combined
    assert state.status == ClaimsIntakeStatus.ADJUSTER_ASSIGNED
    assert state.claim_reference is not None


async def test_inactive_policy_does_not_block_registration() -> None:
    state, notices = await advance_claims_intake(
        _ready_state("SYN-POL-0003"), "confirmed", _build_executor()
    )

    combined = " ".join(notices).lower()
    assert "not active" in combined
    assert state.status == ClaimsIntakeStatus.ADJUSTER_ASSIGNED
    assert state.claim_reference is not None


async def test_unknown_policy_number_blocks_and_asks_to_recheck() -> None:
    state, notices = await advance_claims_intake(
        _ready_state("SYN-POL-9999"), "confirmed", _build_executor()
    )

    assert state.status == ClaimsIntakeStatus.VALIDATING_POLICY
    assert state.claim_reference is None
    assert "could not find a policy" in " ".join(notices).lower()


async def test_supplying_a_corrected_policy_number_after_not_found_retries_validation() -> None:
    executor = _build_executor()
    first_state, _ = await advance_claims_intake(
        _ready_state("SYN-POL-9999"), "confirmed", executor
    )

    second_state, notices = await advance_claims_intake(
        first_state, "sorry, it's SYN-POL-0001", executor
    )

    assert second_state.status == ClaimsIntakeStatus.ADJUSTER_ASSIGNED
    assert second_state.claim_reference is not None
    assert "could not find" not in " ".join(notices).lower()


async def test_a_message_after_adjuster_assignment_does_not_register_a_second_claim() -> None:
    executor = _build_executor()
    registered_state, _ = await advance_claims_intake(
        _ready_state("SYN-POL-0001"), "confirmed", executor
    )
    assert registered_state.status == ClaimsIntakeStatus.ADJUSTER_ASSIGNED
    original_reference = registered_state.claim_reference

    final_state, notices = await advance_claims_intake(
        registered_state, "thanks!", executor
    )

    assert final_state.claim_reference == original_reference
    assert final_state.status == ClaimsIntakeStatus.ADJUSTER_ASSIGNED
    assert "already registered" in " ".join(notices).lower()

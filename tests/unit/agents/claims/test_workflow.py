"""Unit tests for the claims-intake state machine (advance_claims_intake): the dict-dispatched
per-status handlers, driven end-to-end through real synthetic Tools via ToolExecutor. Covers
the four required synthetic policy scenarios, the not-found retry path, and duplicate
registration prevention.

PBI-04-04: the flow now asks for the customer's name first (skipped when a policy number is
given directly), validates policy/payment/coverage, and requires an explicit yes/no
confirmation turn before actually registering the claim. All tests here use language="en"
because they assert on exact English notice text.
"""

import re

from src.agents.claims.state import ClaimsIntakeState, ClaimsIntakeStatus
from src.agents.claims.workflow import advance_claims_intake
from src.services.tools.adjuster_assignment_tool import AdjusterAssignmentTool
from src.services.tools.claim_registration_tool import ClaimRegistrationTool
from src.services.tools.coverage_lookup_tool import CoverageLookupTool
from src.services.tools.customer_lookup_tool import CustomerLookupTool
from src.services.tools.payment_status_tool import PaymentStatusTool
from src.services.tools.policy_lookup_tool import PolicyLookupTool
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry

_CLAIM_REFERENCE_PATTERN = re.compile(r"^SYN-CLM-\d{4}-\d{4}$")


def _build_executor() -> ToolExecutor:
    registry = InMemoryToolRegistry()
    registry.register(CustomerLookupTool())
    registry.register(PolicyLookupTool())
    registry.register(PaymentStatusTool())
    registry.register(CoverageLookupTool())
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
        customer_name="Jane Caller",
        contact_phone="555-123-4567",
        injuries_reported=False,
        third_parties_involved=True,
    )


async def test_new_conversation_asks_for_the_first_missing_field() -> None:
    state, notices = await advance_claims_intake(
        ClaimsIntakeState(), "I need to file a claim", _build_executor(), language="en"
    )

    assert state.status == ClaimsIntakeStatus.COLLECTING_INFORMATION
    assert state.last_asked_field == "customer_name"
    assert len(notices) == 1
    assert "name" in notices[0].lower()


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
        "555-123-4567",
        "no",
        "yes",
        "yes",  # vehicle_drivable (PBI-05-01: auto profile asks this)
        "yes",  # explicit confirmation before registration (PBI-04-04)
    ]

    all_notices: list[str] = []
    for message in turns:
        state, notices = await advance_claims_intake(state, message, executor, language="en")
        all_notices.append(" ".join(notices))

    combined = " ".join(all_notices).lower()
    assert state.status == ClaimsIntakeStatus.ADJUSTER_ASSIGNED
    assert state.claim_reference is not None
    assert _CLAIM_REFERENCE_PATTERN.match(state.claim_reference)
    assert state.adjuster_assigned is not None
    assert "active" in combined
    assert "claim reference is" in combined
    assert "assigned" in all_notices[-1].lower()


async def test_active_policy_with_payment_issue_does_not_block_registration() -> None:
    executor = _build_executor()
    state, notices = await advance_claims_intake(
        _ready_state("SYN-POL-0002"), "confirmed", executor, language="en"
    )

    combined = " ".join(notices).lower()
    assert "payment issue" in combined
    assert state.status == ClaimsIntakeStatus.CONFIRMING

    final_state, final_notices = await advance_claims_intake(state, "yes", executor, language="en")

    assert final_state.status == ClaimsIntakeStatus.ADJUSTER_ASSIGNED
    assert final_state.claim_reference is not None
    assert "assigned" in " ".join(final_notices).lower()


async def test_inactive_policy_does_not_block_registration() -> None:
    executor = _build_executor()
    state, notices = await advance_claims_intake(
        _ready_state("SYN-POL-0003"), "confirmed", executor, language="en"
    )

    combined = " ".join(notices).lower()
    assert "not active" in combined
    assert state.status == ClaimsIntakeStatus.CONFIRMING

    final_state, final_notices = await advance_claims_intake(state, "yes", executor, language="en")

    assert final_state.status == ClaimsIntakeStatus.ADJUSTER_ASSIGNED
    assert final_state.claim_reference is not None
    assert "assigned" in " ".join(final_notices).lower()


async def test_unknown_policy_number_blocks_and_asks_to_recheck() -> None:
    state, notices = await advance_claims_intake(
        _ready_state("SYN-POL-9999"), "confirmed", _build_executor(), language="en"
    )

    assert state.status == ClaimsIntakeStatus.VALIDATING_POLICY
    assert state.claim_reference is None
    assert "could not find a policy" in " ".join(notices).lower()


async def test_supplying_a_corrected_policy_number_after_not_found_retries_validation() -> None:
    executor = _build_executor()
    first_state, _ = await advance_claims_intake(
        _ready_state("SYN-POL-9999"), "confirmed", executor, language="en"
    )

    second_state, notices = await advance_claims_intake(
        first_state, "sorry, it's SYN-POL-0001", executor, language="en"
    )

    assert second_state.status == ClaimsIntakeStatus.CONFIRMING
    assert "could not find" not in " ".join(notices).lower()

    third_state, third_notices = await advance_claims_intake(
        second_state, "yes", executor, language="en"
    )

    assert third_state.status == ClaimsIntakeStatus.ADJUSTER_ASSIGNED
    assert third_state.claim_reference is not None
    assert "assigned" in " ".join(third_notices).lower()


async def test_a_message_after_adjuster_assignment_does_not_register_a_second_claim() -> None:
    executor = _build_executor()
    confirming_state, _ = await advance_claims_intake(
        _ready_state("SYN-POL-0001"), "confirmed", executor, language="en"
    )
    assert confirming_state.status == ClaimsIntakeStatus.CONFIRMING

    registered_state, _ = await advance_claims_intake(
        confirming_state, "yes", executor, language="en"
    )
    assert registered_state.status == ClaimsIntakeStatus.ADJUSTER_ASSIGNED
    original_reference = registered_state.claim_reference

    final_state, notices = await advance_claims_intake(
        registered_state, "thanks!", executor, language="en"
    )

    assert final_state.claim_reference == original_reference
    assert final_state.status == ClaimsIntakeStatus.ADJUSTER_ASSIGNED
    assert "already registered" in " ".join(notices).lower()


# ---------------------------------------------------------------------------
# PBI-05-01: natural Spanish multi-fact extraction, line-of-business-aware
# profiles, and the shared Conversational Policy's opening acknowledgment.
# ---------------------------------------------------------------------------


async def test_opening_message_with_loss_type_triggers_empathetic_acknowledgment() -> None:
    state, notices = await advance_claims_intake(
        ClaimsIntakeState(), "Se inundó mi casa.", _build_executor(), language="es-MX"
    )

    response = " ".join(notices)
    assert "Lamento lo ocurrido" in response
    assert "inundación" in response
    assert "¿A nombre de quién está la póliza?" in response
    assert state.opening_acknowledged is True
    # loss_type was already extracted from the opening message — never asked again later.
    assert state.loss_type == "water damage"


async def test_opening_message_without_loss_type_uses_a_bare_lead_in() -> None:
    state, notices = await advance_claims_intake(
        ClaimsIntakeState(), "Quiero reportar un siniestro.", _build_executor(), language="es-MX"
    )

    response = " ".join(notices)
    assert response.startswith("Claro.")
    assert "Lamento lo ocurrido" not in response
    assert state.opening_acknowledged is True


async def test_acknowledgment_is_never_repeated_on_a_later_turn() -> None:
    executor = _build_executor()
    state, _ = await advance_claims_intake(
        ClaimsIntakeState(), "Se inundó mi casa.", executor, language="es-MX"
    )
    assert state.status == ClaimsIntakeStatus.COLLECTING_INFORMATION
    assert state.customer_name is None

    _, second_notices = await advance_claims_intake(state, "Ana Torres", executor, language="es-MX")

    assert "Lamento lo ocurrido" not in " ".join(second_notices)


async def test_auto_claim_via_customer_discovery_never_asks_property_questions() -> None:
    """The exact SCENARIO A shape from PBI-05-01: name -> disambiguate by vehicle -> one rich
    message carrying date/location/loss_type/injuries/third_parties/vehicle_drivable all at
    once (relative date "ayer" included) -> only a phone number is still missing."""
    executor = _build_executor()
    state, _ = await advance_claims_intake(
        ClaimsIntakeState(), "Quiero reportar un siniestro.", executor, language="es-MX"
    )
    state, _ = await advance_claims_intake(state, "Juan Pérez", executor, language="es-MX")
    state, _ = await advance_claims_intake(state, "la Hilux", executor, language="es-MX")
    assert state.policy_number == "SYN-POL-1002"
    assert state.line_of_business == "auto"

    state, notices = await advance_claims_intake(
        state,
        "Ayer me chocaron por atrás en Reforma. No hubo lesionados ni terceros y el "
        "vehículo todavía puede circular.",
        executor,
        language="es-MX",
    )

    assert state.event_date is not None  # "ayer" resolved to a real date
    assert state.event_location and "reforma" in state.event_location.lower()
    assert state.loss_type == "collision"
    assert state.injuries_reported is False
    assert state.third_parties_involved is False
    assert state.vehicle_drivable is True
    # Only loss_description and contact_phone remain — never a property question.
    response = " ".join(notices).lower()
    assert "propiedad" not in response
    assert "habitable" not in response


async def test_property_claim_via_customer_discovery_never_asks_vehicle_questions() -> None:
    """The exact SCENARIO B shape from PBI-05-01."""
    executor = _build_executor()
    state, _ = await advance_claims_intake(
        ClaimsIntakeState(),
        "Ayer llovió muy fuerte y se inundó mi casa.",
        executor,
        language="es-MX",
    )
    assert state.loss_type == "water damage"

    state, _ = await advance_claims_intake(state, "Ana Torres", executor, language="es-MX")
    assert state.policy_number == "SYN-POL-1003"
    assert state.line_of_business == "property"

    state, notices = await advance_claims_intake(
        state,
        "Se dañaron los muebles de la sala, no hubo lesionados y todavía podemos "
        "permanecer en la casa.",
        executor,
        language="es-MX",
    )

    assert state.injuries_reported is False
    assert state.property_habitable is True
    response = " ".join(notices).lower()
    assert "vehículo" not in response
    assert "circular" not in response


async def test_lapsed_policy_reachable_through_natural_customer_discovery() -> None:
    """Carlos Mendoza's lapsed policy (PBI-05-01 synthetic-data expansion) — reachable by name,
    not just a direct policy number, and lapsed status surfaces as a fact, never blocks."""
    executor = _build_executor()
    state, _ = await advance_claims_intake(
        ClaimsIntakeState(), "Quiero reportar un siniestro.", executor, language="es-MX"
    )
    state, notices = await advance_claims_intake(state, "Carlos Mendoza", executor, language="es-MX")

    assert state.policy_number == "SYN-POL-1004"
    assert "honda cr-v" in " ".join(notices).lower()

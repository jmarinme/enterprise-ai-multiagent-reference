"""Claims-intake state machine (PBI-01-05).

Dict-dispatched per-status handlers, each returning the (possibly updated) state, the
user-facing notices produced this step, and whether the loop should immediately continue into
the next status within the same turn. No if/elif chain selects behavior — resolution is a
single dict lookup, mirroring the registry pattern already used by
src.supervisor.registry.AgentRegistry and src.tools.registry.ToolRegistry.

Only a "policy not found" failure blocks progression. An inactive policy or a payment issue is
surfaced as a fact and does not block claim registration — the Agent gathers and reports facts,
it never approves, rejects, or adjudicates coverage (CLAUDE.md §2).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from src.agents.claims.extraction import extract_fields
from src.agents.claims.state import (
    FIELD_PROMPTS,
    ClaimsIntakeState,
    ClaimsIntakeStatus,
    missing_required_fields,
)
from src.tools.executor import ToolExecutor
from src.tools.models import ToolRequest

_ToolContext = dict[str, str | None]
_HandlerResult = tuple[ClaimsIntakeState, list[str], bool]
_Handler = Callable[[ClaimsIntakeState, ToolExecutor, _ToolContext], Awaitable[_HandlerResult]]


async def advance_claims_intake(
    state: ClaimsIntakeState,
    message: str,
    tool_executor: ToolExecutor,
    correlation_id: str | None = None,
    conversation_id: str | None = None,
    user_id: str | None = None,
) -> tuple[ClaimsIntakeState, list[str]]:
    """Extract any recognizable fields from message, then drive the state machine forward
    until it needs more information from the user. Returns the updated state and the ordered
    list of user-facing notices produced this turn."""
    current_state = extract_fields(message, state)
    tool_context: _ToolContext = {
        "correlation_id": correlation_id,
        "conversation_id": conversation_id,
        "user_id": user_id,
    }
    notices: list[str] = []

    while True:
        handler = _HANDLERS[current_state.status]
        current_state, new_notices, should_continue = await handler(
            current_state, tool_executor, tool_context
        )
        notices.extend(new_notices)
        if not should_continue:
            break

    return current_state, notices


async def _handle_new(
    state: ClaimsIntakeState, _tool_executor: ToolExecutor, _ctx: _ToolContext
) -> _HandlerResult:
    return state.model_copy(update={"status": ClaimsIntakeStatus.COLLECTING_INFORMATION}), [], True


async def _handle_collecting_information(
    state: ClaimsIntakeState, _tool_executor: ToolExecutor, _ctx: _ToolContext
) -> _HandlerResult:
    missing = missing_required_fields(state)
    if missing:
        next_field = missing[0]
        new_state = state.model_copy(update={"last_asked_field": next_field})
        return new_state, [FIELD_PROMPTS[next_field]], False

    new_state = state.model_copy(
        update={"status": ClaimsIntakeStatus.VALIDATING_POLICY, "last_asked_field": None}
    )
    return new_state, [], True


async def _handle_validating_policy(
    state: ClaimsIntakeState, tool_executor: ToolExecutor, ctx: _ToolContext
) -> _HandlerResult:
    policy_result = await tool_executor.execute(
        ToolRequest(
            tool_name="policy_lookup",
            tool_input={"policy_number": state.policy_number},
            **ctx,
        )
    )
    if not policy_result.success or policy_result.data is None:
        notice = (
            f"We could not find a policy with number '{state.policy_number}'. "
            "Could you double-check and provide it again?"
        )
        return state, [notice], False

    policy_active = policy_result.data.status == "active"

    payment_result = await tool_executor.execute(
        ToolRequest(
            tool_name="payment_status",
            tool_input={"policy_number": state.policy_number},
            **ctx,
        )
    )
    payment_current = (
        payment_result.data.payment_current
        if payment_result.success and payment_result.data is not None
        else None
    )

    notices: list[str] = []
    if policy_active:
        notices.append("Your policy is active.")
    else:
        notices.append(
            f"Note: this policy's status is currently '{policy_result.data.status}', not "
            "active. We'll still record your claim notice."
        )
    if payment_current is True:
        notices.append("Payments on this policy are up to date.")
    elif payment_current is False:
        notices.append(
            "Note: this policy has an outstanding payment issue. We'll still record your "
            "claim notice."
        )
    else:
        notices.append("We could not confirm this policy's payment status.")

    new_state = state.model_copy(
        update={
            "policy_validated": True,
            "policy_active": policy_active,
            "payment_current": payment_current,
            "status": ClaimsIntakeStatus.READY_TO_REGISTER,
        }
    )
    return new_state, notices, True


async def _handle_ready_to_register(
    state: ClaimsIntakeState, tool_executor: ToolExecutor, ctx: _ToolContext
) -> _HandlerResult:
    result = await tool_executor.execute(
        ToolRequest(
            tool_name="claim_registration",
            tool_input={
                "policy_number": state.policy_number,
                "event_date": state.event_date,
                "event_time": state.event_time,
                "event_location": state.event_location,
                "loss_type": state.loss_type,
                "loss_description": state.loss_description,
                "contact_name": state.contact_name,
                "contact_phone": state.contact_phone,
                "contact_email": state.contact_email,
                "injuries_reported": bool(state.injuries_reported),
                "third_parties_involved": bool(state.third_parties_involved),
            },
            **ctx,
        )
    )
    if not result.success or result.data is None:
        notice = "We were unable to register your claim notice right now. Please try again shortly."
        return state, [notice], False

    new_state = state.model_copy(
        update={
            "claim_reference": result.data.claim_reference,
            "status": ClaimsIntakeStatus.REGISTERED,
        }
    )
    notice = f"Your claim notice has been registered. Your claim reference is {result.data.claim_reference}."
    return new_state, [notice], True


async def _handle_registered(
    state: ClaimsIntakeState, tool_executor: ToolExecutor, ctx: _ToolContext
) -> _HandlerResult:
    result = await tool_executor.execute(
        ToolRequest(
            tool_name="adjuster_assignment",
            tool_input={"claim_reference": state.claim_reference},
            **ctx,
        )
    )
    if not result.success or result.data is None:
        notice = (
            f"Your claim {state.claim_reference} is registered. Adjuster assignment is "
            "pending — we'll follow up shortly."
        )
        return state, [notice], False

    new_state = state.model_copy(
        update={
            "adjuster_assigned": result.data.adjuster_name,
            "status": ClaimsIntakeStatus.ADJUSTER_ASSIGNED,
        }
    )
    notice = (
        f"{result.data.adjuster_name} has been assigned to your claim "
        f"{state.claim_reference} and will contact you soon."
    )
    return new_state, [notice], False


async def _handle_adjuster_assigned(
    state: ClaimsIntakeState, _tool_executor: ToolExecutor, _ctx: _ToolContext
) -> _HandlerResult:
    notice = (
        f"Your claim {state.claim_reference} is already registered and assigned to "
        f"{state.adjuster_assigned}. No further action is needed from you right now."
    )
    return state, [notice], False


_HANDLERS: dict[ClaimsIntakeStatus, _Handler] = {
    ClaimsIntakeStatus.NEW: _handle_new,
    ClaimsIntakeStatus.COLLECTING_INFORMATION: _handle_collecting_information,
    ClaimsIntakeStatus.VALIDATING_POLICY: _handle_validating_policy,
    ClaimsIntakeStatus.READY_TO_REGISTER: _handle_ready_to_register,
    ClaimsIntakeStatus.REGISTERED: _handle_registered,
    ClaimsIntakeStatus.ADJUSTER_ASSIGNED: _handle_adjuster_assigned,
}

"""Commercial-intake state machine (PBI-01-07, bilingual notices added by PBI-04-04).

Dict-dispatched per-status handlers, mirroring src.agents.claims.workflow's single-linear-flow
shape (there is no branching "inquiry type" here, unlike Broker). No if/elif chain selects
behavior — resolution is a single dict lookup.

This Agent only collects and registers a synthetic lead — it never quotes, underwrites, defines
premiums, or guarantees acceptance (CLAUDE.md §2).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from src.agents.commercial.extraction import extract_fields
from src.agents.commercial.state import (
    FIELD_PROMPTS,
    CommercialIntakeState,
    CommercialIntakeStatus,
    missing_required_fields,
)
from src.agents.shared.language import Language
from src.agents.shared.messages import t
from src.tools.executor import ToolExecutor
from src.tools.models import ToolRequest

_ToolContext = dict[str, str | None]
_HandlerResult = tuple[CommercialIntakeState, list[str], bool]
_Handler = Callable[
    [CommercialIntakeState, ToolExecutor, _ToolContext, Language], Awaitable[_HandlerResult]
]

_MESSAGES: dict[str, dict[Language, str]] = {
    "registration_failed": {
        "es-MX": "No pudimos registrar tu solicitud en este momento. Intenta de nuevo en breve.",
        "en": "We were unable to register your inquiry right now. Please try again shortly.",
    },
    "registration_success": {
        "es-MX": (
            "Gracias — tu solicitud ha sido registrada. Tu número de referencia es "
            "{lead_reference}. Un representante te contactará por {channel}."
        ),
        "en": (
            "Thank you — your inquiry has been registered. Your reference is {lead_reference}. "
            "A representative will follow up via {channel}."
        ),
    },
    "already_registered": {
        "es-MX": (
            "Tu solicitud ya está registrada. Tu número de referencia es {lead_reference}. No "
            "necesitas hacer nada más por ahora."
        ),
        "en": (
            "Your inquiry is already registered. Your reference is {lead_reference}. No "
            "further action is needed from you right now."
        ),
    },
}

_CHANNEL_LABELS: dict[str, dict[Language, str]] = {
    "email": {"es-MX": "correo electrónico", "en": "email"},
    "phone": {"es-MX": "teléfono", "en": "phone"},
}


async def advance_commercial_intake(
    state: CommercialIntakeState,
    message: str,
    tool_executor: ToolExecutor,
    language: Language,
    correlation_id: str | None = None,
    conversation_id: str | None = None,
    user_id: str | None = None,
) -> tuple[CommercialIntakeState, list[str]]:
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
            current_state, tool_executor, tool_context, language
        )
        notices.extend(new_notices)
        if not should_continue:
            break

    return current_state, notices


async def _handle_new(
    state: CommercialIntakeState, _tool_executor: ToolExecutor, _ctx: _ToolContext, _language: Language
) -> _HandlerResult:
    return (
        state.model_copy(update={"status": CommercialIntakeStatus.COLLECTING_INFORMATION}),
        [],
        True,
    )


async def _handle_collecting_information(
    state: CommercialIntakeState, _tool_executor: ToolExecutor, _ctx: _ToolContext, language: Language
) -> _HandlerResult:
    missing = missing_required_fields(state)
    if missing:
        next_field = missing[0]
        new_state = state.model_copy(update={"last_asked_field": next_field})
        return new_state, [t(FIELD_PROMPTS, next_field, language)], False

    new_state = state.model_copy(
        update={"status": CommercialIntakeStatus.READY_TO_REGISTER, "last_asked_field": None}
    )
    return new_state, [], True


async def _handle_ready_to_register(
    state: CommercialIntakeState, tool_executor: ToolExecutor, ctx: _ToolContext, language: Language
) -> _HandlerResult:
    result = await tool_executor.execute(
        ToolRequest(
            tool_name="lead_registration",
            tool_input={
                "company_name": state.company_name,
                "contact_name": state.contact_name,
                "preferred_contact_channel": state.preferred_contact_channel,
                "insurance_need": state.insurance_need,
                "risk_description": state.risk_description,
                "contact_email": state.contact_email,
                "contact_phone": state.contact_phone,
            },
            **ctx,
        )
    )
    if not result.success or result.data is None:
        notice = t(_MESSAGES, "registration_failed", language)
        return state, [notice], False

    new_state = state.model_copy(
        update={
            "lead_reference": result.data.lead_reference,
            "status": CommercialIntakeStatus.REGISTERED,
        }
    )
    channel = state.preferred_contact_channel or ""
    channel_label = t(_CHANNEL_LABELS, channel, language) if channel in _CHANNEL_LABELS else channel
    notice = t(
        _MESSAGES,
        "registration_success",
        language,
        lead_reference=result.data.lead_reference,
        channel=channel_label,
    )
    return new_state, [notice], False


async def _handle_registered(
    state: CommercialIntakeState, _tool_executor: ToolExecutor, _ctx: _ToolContext, language: Language
) -> _HandlerResult:
    notice = t(_MESSAGES, "already_registered", language, lead_reference=state.lead_reference)
    return state, [notice], False


_HANDLERS: dict[CommercialIntakeStatus, _Handler] = {
    CommercialIntakeStatus.NEW: _handle_new,
    CommercialIntakeStatus.COLLECTING_INFORMATION: _handle_collecting_information,
    CommercialIntakeStatus.READY_TO_REGISTER: _handle_ready_to_register,
    CommercialIntakeStatus.REGISTERED: _handle_registered,
}

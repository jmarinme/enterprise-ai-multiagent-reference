"""Broker-services state machine (PBI-01-06, bilingual notices added by PBI-04-04).

Dict-dispatched per-status handlers, consistent with src.agents.claims.workflow's pattern — no
if/elif chain selects behavior. The commission-payment sub-flow the PBI suggests as a separate
parallel state machine is folded into this single state machine instead (READY_TO_RESPOND ->
READY_TO_REQUEST_PAYMENT -> PAYMENT_REQUEST_REGISTERED): a commission lookup and a payment
request share the same broker_id/commission_period fields, so a second, separately-driven state
machine would duplicate the collection step for no benefit.

A lookup failure (broker/policy/transaction not found, or no commission for that period) never
resets the collected fields — it stays in LOOKING_UP_DATA so the very next message can simply
supply a corrected ID and retry, mirroring src.agents.claims.workflow's "policy not found"
handling exactly.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from src.agents.broker.extraction import extract_fields
from src.agents.broker.state import (
    BrokerInquiryState,
    BrokerInquiryStatus,
    BrokerInquiryType,
    missing_required_fields,
    prompt_for_missing,
)
from src.agents.shared.language import Language
from src.agents.shared.messages import t
from src.tools.executor import ToolExecutor
from src.tools.models import ToolRequest

_ToolContext = dict[str, str | None]
_HandlerResult = tuple[BrokerInquiryState, list[str], bool]
_Handler = Callable[
    [BrokerInquiryState, ToolExecutor, _ToolContext, Language], Awaitable[_HandlerResult]
]

_MESSAGES: dict[str, dict[Language, str]] = {
    "ask_inquiry_type": {
        "es-MX": (
            "¿En qué te puedo ayudar — consultar el estado de una póliza o transacción, o "
            "revisar tus comisiones?"
        ),
        "en": (
            "What would you like help with — checking a policy or transaction status, or "
            "reviewing your commissions?"
        ),
    },
    "policy_not_found": {
        "es-MX": (
            "No encontramos una póliza con el número '{policy_number}'. ¿Puedes verificarlo y "
            "proporcionarlo de nuevo?"
        ),
        "en": (
            "We could not find a policy with number '{policy_number}'. Could you double-check "
            "and provide it again?"
        ),
    },
    "policy_status": {
        "es-MX": "Estado de la póliza {policy_number}: {status}.",
        "en": "Policy {policy_number} status: {status}.",
    },
    "payment_current": {
        "es-MX": "Los pagos de esta póliza están al corriente.",
        "en": "Payments on this policy are up to date.",
    },
    "payment_issue": {
        "es-MX": "Esta póliza tiene un pago pendiente.",
        "en": "This policy has an outstanding payment issue.",
    },
    "payment_unknown": {
        "es-MX": "No pudimos confirmar el estado de pago de esta póliza.",
        "en": "We could not confirm this policy's payment status.",
    },
    "transaction_not_found": {
        "es-MX": (
            "No encontramos una transacción con referencia '{transaction_reference}'. ¿Puedes "
            "verificarla y proporcionarla de nuevo?"
        ),
        "en": (
            "We could not find a transaction with reference '{transaction_reference}'. Could "
            "you double-check and provide it again?"
        ),
    },
    "transaction_status": {
        "es-MX": "Estado de la transacción {transaction_reference}: {status}.",
        "en": "Transaction {transaction_reference} status: {status}.",
    },
    "broker_not_found": {
        "es-MX": (
            "No encontramos una cuenta de corredor con ID '{broker_id}'. ¿Puedes verificarlo y "
            "proporcionarlo de nuevo?"
        ),
        "en": (
            "We could not find a broker account with ID '{broker_id}'. Could you double-check "
            "and provide it again?"
        ),
    },
    "commission_not_found": {
        "es-MX": (
            "No encontramos comisiones para el corredor '{broker_id}' en el período "
            "'{commission_period}'. ¿Puedes verificar el período y proporcionarlo de nuevo?"
        ),
        "en": (
            "We could not find commission data for broker '{broker_id}' in period "
            "'{commission_period}'. Could you double-check the period and provide it again?"
        ),
    },
    "commission_summary": {
        "es-MX": "Comisión de {commission_period}: ${amount:,.2f} (estado: {status}).",
        "en": "Commission for {commission_period}: ${amount:,.2f} (status: {status}).",
    },
    "ask_payment_request": {
        "es-MX": "¿Te gustaría solicitar el pago de esta comisión? (sí/no)",
        "en": "Would you like to request payment for this commission? (yes/no)",
    },
    "payment_request_failed": {
        "es-MX": (
            "No pudimos registrar tu solicitud de pago de comisión en este momento. Intenta de "
            "nuevo en breve."
        ),
        "en": (
            "We were unable to register your commission payment request right now. Please try "
            "again shortly."
        ),
    },
    "payment_request_registered": {
        "es-MX": "Tu solicitud de pago de comisión ha sido registrada. Referencia: {reference}.",
        "en": "Your commission payment request has been registered. Reference: {reference}.",
    },
    "payment_request_already_registered": {
        "es-MX": "Ya existe una solicitud de pago registrada para esta comisión. Referencia: {reference}.",
        "en": "A payment request for this commission is already registered. Reference: {reference}.",
    },
    "summary_policy": {
        "es-MX": "Estado de la póliza {policy_number}: {status}. Esta solicitud está completa.",
        "en": "Policy {policy_number} status: {status}. This request is complete.",
    },
    "summary_transaction": {
        "es-MX": (
            "Estado de la transacción {transaction_reference}: {status}. Esta solicitud está "
            "completa."
        ),
        "en": "Transaction {transaction_reference} status: {status}. This request is complete.",
    },
    "summary_commission": {
        "es-MX": "Comisión de {commission_period}: estado {status}. Esta solicitud está completa.",
        "en": "Commission for {commission_period}: status {status}. This request is complete.",
    },
    "summary_generic": {
        "es-MX": "Esta solicitud está completa.",
        "en": "This request is complete.",
    },
}


async def advance_broker_inquiry(
    state: BrokerInquiryState,
    message: str,
    tool_executor: ToolExecutor,
    language: Language,
    correlation_id: str | None = None,
    conversation_id: str | None = None,
    user_id: str | None = None,
) -> tuple[BrokerInquiryState, list[str]]:
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
    state: BrokerInquiryState, _tool_executor: ToolExecutor, _ctx: _ToolContext, _language: Language
) -> _HandlerResult:
    return state.model_copy(update={"status": BrokerInquiryStatus.IDENTIFYING_REQUEST}), [], True


async def _handle_identifying_request(
    state: BrokerInquiryState, _tool_executor: ToolExecutor, _ctx: _ToolContext, language: Language
) -> _HandlerResult:
    if state.inquiry_type is None:
        notice = t(_MESSAGES, "ask_inquiry_type", language)
        return state, [notice], False

    new_state = state.model_copy(update={"status": BrokerInquiryStatus.COLLECTING_INFORMATION})
    return new_state, [], True


async def _handle_collecting_information(
    state: BrokerInquiryState, _tool_executor: ToolExecutor, _ctx: _ToolContext, language: Language
) -> _HandlerResult:
    missing = missing_required_fields(state)
    if missing:
        new_state = state.model_copy(update={"next_required_fields": missing})
        return new_state, [prompt_for_missing(missing, language)], False

    new_state = state.model_copy(
        update={"status": BrokerInquiryStatus.LOOKING_UP_DATA, "next_required_fields": []}
    )
    return new_state, [], True


async def _handle_looking_up_data(
    state: BrokerInquiryState, tool_executor: ToolExecutor, ctx: _ToolContext, language: Language
) -> _HandlerResult:
    assert state.inquiry_type is not None  # guaranteed by _handle_identifying_request
    lookup = _LOOKUP_HANDLERS[state.inquiry_type]
    return await lookup(state, tool_executor, ctx, language)


async def _lookup_policy_status(
    state: BrokerInquiryState, tool_executor: ToolExecutor, ctx: _ToolContext, language: Language
) -> _HandlerResult:
    policy_result = await tool_executor.execute(
        ToolRequest(tool_name="policy_lookup", tool_input={"policy_number": state.policy_number}, **ctx)
    )
    if not policy_result.success or policy_result.data is None:
        notice = t(_MESSAGES, "policy_not_found", language, policy_number=state.policy_number)
        return state, [notice], False

    payment_result = await tool_executor.execute(
        ToolRequest(
            tool_name="payment_status", tool_input={"policy_number": state.policy_number}, **ctx
        )
    )
    payment_current = (
        payment_result.data.payment_current
        if payment_result.success and payment_result.data is not None
        else None
    )

    notices = [
        t(_MESSAGES, "policy_status", language, policy_number=state.policy_number, status=policy_result.data.status)
    ]
    if payment_current is True:
        notices.append(t(_MESSAGES, "payment_current", language))
    elif payment_current is False:
        notices.append(t(_MESSAGES, "payment_issue", language))
    else:
        notices.append(t(_MESSAGES, "payment_unknown", language))

    new_state = state.model_copy(
        update={
            "policy_status": policy_result.data.status,
            "policy_payment_current": payment_current,
            "status": BrokerInquiryStatus.READY_TO_RESPOND,
        }
    )
    return new_state, notices, True


async def _lookup_transaction_status(
    state: BrokerInquiryState, tool_executor: ToolExecutor, ctx: _ToolContext, language: Language
) -> _HandlerResult:
    result = await tool_executor.execute(
        ToolRequest(
            tool_name="transaction_status",
            tool_input={"transaction_reference": state.transaction_reference},
            **ctx,
        )
    )
    if not result.success or result.data is None:
        notice = t(
            _MESSAGES,
            "transaction_not_found",
            language,
            transaction_reference=state.transaction_reference,
        )
        return state, [notice], False

    notice = t(
        _MESSAGES,
        "transaction_status",
        language,
        transaction_reference=state.transaction_reference,
        status=result.data.status,
    )
    new_state = state.model_copy(
        update={"transaction_status": result.data.status, "status": BrokerInquiryStatus.READY_TO_RESPOND}
    )
    return new_state, [notice], True


async def _lookup_commission(
    state: BrokerInquiryState, tool_executor: ToolExecutor, ctx: _ToolContext, language: Language
) -> _HandlerResult:
    broker_result = await tool_executor.execute(
        ToolRequest(tool_name="broker_account_lookup", tool_input={"broker_id": state.broker_id}, **ctx)
    )
    if not broker_result.success or broker_result.data is None:
        notice = t(_MESSAGES, "broker_not_found", language, broker_id=state.broker_id)
        return state, [notice], False

    commission_result = await tool_executor.execute(
        ToolRequest(
            tool_name="commission_lookup",
            tool_input={"broker_id": state.broker_id, "commission_period": state.commission_period},
            **ctx,
        )
    )
    if not commission_result.success or commission_result.data is None:
        notice = t(
            _MESSAGES,
            "commission_not_found",
            language,
            broker_id=state.broker_id,
            commission_period=state.commission_period,
        )
        return state, [notice], False

    notice = t(
        _MESSAGES,
        "commission_summary",
        language,
        commission_period=state.commission_period,
        amount=commission_result.data.amount,
        status=commission_result.data.status,
    )
    new_state = state.model_copy(
        update={
            "broker_active": broker_result.data.status == "active",
            "commission_amount": commission_result.data.amount,
            "commission_status": commission_result.data.status,
            "status": BrokerInquiryStatus.READY_TO_RESPOND,
        }
    )
    return new_state, [notice], True


_LOOKUP_HANDLERS: dict[BrokerInquiryType, _Handler] = {
    BrokerInquiryType.POLICY_STATUS: _lookup_policy_status,
    BrokerInquiryType.TRANSACTION_STATUS: _lookup_transaction_status,
    BrokerInquiryType.COMMISSION: _lookup_commission,
}


async def _handle_ready_to_respond(
    state: BrokerInquiryState, _tool_executor: ToolExecutor, _ctx: _ToolContext, language: Language
) -> _HandlerResult:
    if state.inquiry_type == BrokerInquiryType.COMMISSION and state.commission_status == "available":
        if state.wants_payment_request is None:
            notice = t(_MESSAGES, "ask_payment_request", language)
            new_state = state.model_copy(update={"last_asked_field": "wants_payment_request"})
            return new_state, [notice], False
        if state.wants_payment_request:
            new_state = state.model_copy(update={"status": BrokerInquiryStatus.READY_TO_REQUEST_PAYMENT})
            return new_state, [], True

    # should_continue=False (not True): the lookup handler already reported the relevant
    # facts this turn. _handle_completed's summary is for a *later* turn re-visiting a
    # finished conversation, not an immediate repeat of what was just said.
    new_state = state.model_copy(update={"status": BrokerInquiryStatus.COMPLETED})
    return new_state, [], False


async def _handle_ready_to_request_payment(
    state: BrokerInquiryState, tool_executor: ToolExecutor, ctx: _ToolContext, language: Language
) -> _HandlerResult:
    result = await tool_executor.execute(
        ToolRequest(
            tool_name="commission_payment_request",
            tool_input={"broker_id": state.broker_id, "commission_period": state.commission_period},
            **ctx,
        )
    )
    if not result.success or result.data is None:
        notice = t(_MESSAGES, "payment_request_failed", language)
        return state, [notice], False

    new_state = state.model_copy(
        update={
            "payment_request_reference": result.data.payment_request_reference,
            "status": BrokerInquiryStatus.PAYMENT_REQUEST_REGISTERED,
        }
    )
    notice = t(
        _MESSAGES, "payment_request_registered", language, reference=result.data.payment_request_reference
    )
    return new_state, [notice], False


async def _handle_payment_request_registered(
    state: BrokerInquiryState, _tool_executor: ToolExecutor, _ctx: _ToolContext, language: Language
) -> _HandlerResult:
    notice = t(
        _MESSAGES,
        "payment_request_already_registered",
        language,
        reference=state.payment_request_reference,
    )
    return state, [notice], False


async def _handle_completed(
    state: BrokerInquiryState, _tool_executor: ToolExecutor, _ctx: _ToolContext, language: Language
) -> _HandlerResult:
    return state, [_summary_notice(state, language)], False


def _summary_notice(state: BrokerInquiryState, language: Language) -> str:
    if state.inquiry_type == BrokerInquiryType.POLICY_STATUS:
        return t(
            _MESSAGES, "summary_policy", language, policy_number=state.policy_number, status=state.policy_status
        )
    if state.inquiry_type == BrokerInquiryType.TRANSACTION_STATUS:
        return t(
            _MESSAGES,
            "summary_transaction",
            language,
            transaction_reference=state.transaction_reference,
            status=state.transaction_status,
        )
    if state.inquiry_type == BrokerInquiryType.COMMISSION:
        return t(
            _MESSAGES,
            "summary_commission",
            language,
            commission_period=state.commission_period,
            status=state.commission_status,
        )
    return t(_MESSAGES, "summary_generic", language)


_HANDLERS: dict[BrokerInquiryStatus, _Handler] = {
    BrokerInquiryStatus.NEW: _handle_new,
    BrokerInquiryStatus.IDENTIFYING_REQUEST: _handle_identifying_request,
    BrokerInquiryStatus.COLLECTING_INFORMATION: _handle_collecting_information,
    BrokerInquiryStatus.LOOKING_UP_DATA: _handle_looking_up_data,
    BrokerInquiryStatus.READY_TO_RESPOND: _handle_ready_to_respond,
    BrokerInquiryStatus.READY_TO_REQUEST_PAYMENT: _handle_ready_to_request_payment,
    BrokerInquiryStatus.PAYMENT_REQUEST_REGISTERED: _handle_payment_request_registered,
    BrokerInquiryStatus.COMPLETED: _handle_completed,
}

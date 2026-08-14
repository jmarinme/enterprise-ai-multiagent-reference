"""Claims-intake state machine (PBI-01-05, extended by PBI-04-04 with customer discovery,
coverage validation, and an explicit pre-registration confirmation step).

Dict-dispatched per-status handlers, each returning the (possibly updated) state, the
user-facing notices produced this step, and whether the loop should immediately continue into
the next status within the same turn. No if/elif chain selects behavior — resolution is a
single dict lookup, mirroring the registry pattern already used by
src.supervisor.registry.AgentRegistry and src.tools.registry.ToolRegistry.

Only a "not found" failure (customer or policy) blocks progression. An inactive policy or a
payment issue is surfaced as a fact and does not block claim registration — the Agent gathers
and reports facts, it never approves, rejects, or adjudicates coverage (CLAUDE.md §2).

PBI-04-04 requirement 5 ("ClaimsAgent should autonomously orchestrate Customer/Policy/Payment/
Coverage/Knowledge/Claim Registration Tools... do not return to the Supervisor for Claims
operations"): every one of those Tool calls below happens inside this single agent's own
advance_claims_intake loop, across as many statuses as one HTTP turn needs — the Supervisor is
never re-entered mid-flow (see src.supervisor.orchestrator, which calls agent.handle() exactly
once per turn and never inspects or drives Agent-internal state).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from src.agents.claims.extraction import extract_fields, resolve_selection
from src.agents.claims.state import (
    FIELD_PROMPTS,
    ClaimsIntakeState,
    ClaimsIntakeStatus,
    PolicyCandidate,
    next_question_group,
)
from src.agents.shared.confirmation import resolve_confirmation
from src.agents.shared.conversational_policy import opening_acknowledgment
from src.agents.shared.language import Language
from src.agents.shared.messages import t
from src.agents.shared.semantic_merge import apply_semantic_entities
from src.agents.shared.semantic_models import ClaimsSemanticInterpretation
from src.core.tool_provider.protocol import ToolProvider
from src.core.workflow_provider.models import ClaimsWorkflowInput
from src.core.workflow_provider.protocol import ClaimsWorkflowProvider
from src.tools.models import ToolRequest

# Multi-field extraction (PBI-14-03 section 6): the free-text/ambiguous ClaimsIntakeState fields
# a high-confidence semantic interpretation may fill in when this turn's deterministic
# extract_fields() left them empty — never policy_number/line_of_business/coverage/
# policy_validated/claim_reference/adjuster_assigned, which only ever come from a Tool result.
_SEMANTIC_FALLBACK_FIELDS: tuple[str, ...] = (
    "customer_name",
    "event_date",
    "event_time",
    "event_location",
    "loss_type",
    "loss_description",
    "contact_phone",
    "contact_email",
    "injuries_reported",
    "third_parties_involved",
    "vehicle_drivable",
    "property_habitable",
)

_ToolContext = dict[str, str | None]
_HandlerResult = tuple[ClaimsIntakeState, list[str], bool]
_Handler = Callable[
    [ClaimsIntakeState, ToolProvider, _ToolContext, Language], Awaitable[_HandlerResult]
]

_MESSAGES: dict[str, dict[Language, str]] = {
    "customer_not_found": {
        "es-MX": (
            "No encontré ningún cliente con el nombre '{name}'. ¿Podrías verificar tu nombre "
            "completo, o darme directamente tu número de póliza?"
        ),
        "en": (
            "I could not find a customer named '{name}'. Could you double-check your full "
            "name, or provide your policy number directly?"
        ),
    },
    "customer_single_match": {
        "es-MX": "Encontré tu póliza ({line_of_business}{vehicle}).",
        "en": "I found your policy ({line_of_business}{vehicle}).",
    },
    "customer_multiple_matches": {
        "es-MX": "Encontré estas pólizas a tu nombre: {options} ¿Cuál corresponde a tu siniestro?",
        "en": "I found these policies under your name: {options} Which one is this claim about?",
    },
    "selection_not_understood": {
        "es-MX": "No logré identificar cuál póliza elegiste. {options} ¿Cuál corresponde?",
        "en": "I couldn't tell which policy you meant. {options} Which one is it?",
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
    "policy_active": {
        "es-MX": "Tu póliza está vigente.",
        "en": "Your policy is active.",
    },
    "policy_inactive": {
        "es-MX": (
            "Nota: el estado de esta póliza es '{status}', no vigente. Aun así registraremos "
            "tu aviso de siniestro."
        ),
        "en": (
            "Note: this policy's status is currently '{status}', not active. We'll still "
            "record your claim notice."
        ),
    },
    "payment_current": {
        "es-MX": "Los pagos de esta póliza están al corriente.",
        "en": "Payments on this policy are up to date.",
    },
    "payment_issue": {
        "es-MX": (
            "Nota: esta póliza tiene un pago pendiente. Aun así registraremos tu aviso de "
            "siniestro."
        ),
        "en": "Note: this policy has an outstanding payment issue. We'll still record your claim notice.",
    },
    "payment_unknown": {
        "es-MX": "No pudimos confirmar el estado de pago de esta póliza.",
        "en": "We could not confirm this policy's payment status.",
    },
    "coverage_found": {
        "es-MX": (
            "Tu cobertura es '{coverage_type}', con suma asegurada de ${limit:,.2f} y "
            "deducible de ${deductible:,.2f}."
        ),
        "en": (
            "Your coverage is '{coverage_type}', with a limit of ${limit:,.2f} and a "
            "deductible of ${deductible:,.2f}."
        ),
    },
    "coverage_unknown": {
        "es-MX": "No pudimos confirmar el detalle de cobertura de esta póliza.",
        "en": "We could not confirm this policy's coverage detail.",
    },
    "confirmation_summary": {
        "es-MX": (
            "Antes de registrar tu siniestro, confirmemos los datos: póliza {policy_number}, "
            "incidente del {event_date} en {event_location}, tipo '{loss_type}'.{lob_detail} "
            "¿Confirmas que deseamos registrar tu siniestro con esta información? (sí/no)"
        ),
        "en": (
            "Before registering your claim, let's confirm the details: policy {policy_number}, "
            "incident on {event_date} at {event_location}, type '{loss_type}'.{lob_detail} "
            "Shall I go ahead and register your claim with this information? (yes/no)"
        ),
    },
    "confirmation_detail_vehicle_drivable": {
        "es-MX": " El vehículo puede circular.",
        "en": " The vehicle is drivable.",
    },
    "confirmation_detail_vehicle_not_drivable": {
        "es-MX": " El vehículo no puede circular.",
        "en": " The vehicle is not drivable.",
    },
    "confirmation_detail_habitable": {
        "es-MX": " La propiedad sigue siendo habitable.",
        "en": " The property remains habitable.",
    },
    "confirmation_detail_not_habitable": {
        "es-MX": " La propiedad no es habitable por ahora.",
        "en": " The property is not currently habitable.",
    },
    "confirmation_declined": {
        "es-MX": "De acuerdo, no lo registraré todavía. ¿Qué dato te gustaría corregir?",
        "en": "Understood, I won't register it yet. What would you like to correct?",
    },
    "registration_failed": {
        "es-MX": "No pudimos registrar tu aviso de siniestro en este momento. Intenta de nuevo en breve.",
        "en": "We were unable to register your claim notice right now. Please try again shortly.",
    },
    "registration_success": {
        "es-MX": "Tu aviso de siniestro ha sido registrado. Tu número de referencia es {claim_reference}.",
        "en": "Your claim notice has been registered. Your claim reference is {claim_reference}.",
    },
    "adjuster_pending": {
        "es-MX": (
            "Tu siniestro {claim_reference} está registrado. La asignación de ajustador está "
            "pendiente — te contactaremos pronto."
        ),
        "en": (
            "Your claim {claim_reference} is registered. Adjuster assignment is pending — "
            "we'll follow up shortly."
        ),
    },
    "adjuster_assigned": {
        "es-MX": "{adjuster_name} fue asignado a tu siniestro {claim_reference} y te contactará pronto.",
        "en": "{adjuster_name} has been assigned to your claim {claim_reference} and will contact you soon.",
    },
    "already_assigned": {
        "es-MX": (
            "Tu siniestro {claim_reference} ya está registrado y asignado a {adjuster_name}. "
            "No necesitas hacer nada más por ahora."
        ),
        "en": (
            "Your claim {claim_reference} is already registered and assigned to "
            "{adjuster_name}. No further action is needed from you right now."
        ),
    },
    "customer_default_name": {
        "es-MX": "Cliente",
        "en": "Customer",
    },
}

# Natural, hand-written combined phrasings for the two multi-field groups defined in
# state.FIELD_GROUPS (PBI-04-04 "group related questions" requirement) — reads far better than
# mechanically concatenating each field's individual FIELD_PROMPTS entry.
_INCIDENT_DETAILS_GROUP = {"event_date", "event_location", "loss_type"}
_YES_NO_GROUP = {"injuries_reported", "third_parties_involved"}
_COMBINED_PROMPTS: dict[str, dict[Language, str]] = {
    "incident_details": {
        "es-MX": (
            "Cuéntame sobre el incidente: ¿qué día ocurrió (AAAA-MM-DD), dónde fue, y qué tipo "
            "de siniestro es (colisión, robo, incendio, daño por agua, clima, vandalismo, otro)?"
        ),
        "en": (
            "Tell me about the incident: what date did it occur (YYYY-MM-DD), where did it "
            "happen, and what type of loss is it (collision, theft, fire, water damage, "
            "weather, vandalism, other)?"
        ),
    },
    "injuries_and_third_parties": {
        "es-MX": "¿Hubo personas lesionadas, y estuvieron involucrados terceros? (sí/no para cada una)",
        "en": "Were there any injuries, and were any third parties involved? (yes/no for each)",
    },
}


async def advance_claims_intake(
    state: ClaimsIntakeState,
    message: str,
    tool_provider: ToolProvider,
    language: Language,
    correlation_id: str | None = None,
    conversation_id: str | None = None,
    user_id: str | None = None,
    workflow_provider: ClaimsWorkflowProvider | None = None,
    semantic: ClaimsSemanticInterpretation | None = None,
) -> tuple[ClaimsIntakeState, list[str]]:
    """Extract any recognizable fields from message, then drive the state machine forward
    until it needs more information from the user. Returns the updated state and the ordered
    list of user-facing notices produced this turn.

    workflow_provider (PBI-06-01, default None): when supplied, READY_TO_REGISTER is handled by
    _handle_ready_to_register_workflow instead of the default in-process
    _handle_ready_to_register/_handle_registered pair — the caller's ClaimsWorkflowProvider
    (in-process or Durable Functions) then owns claim registration + adjuster assignment as one
    transaction, started only after the user has confirmed. Conversational state (this function,
    ClaimsIntakeState) never moves into the workflow — only the already-collected, already-
    confirmed fields do (see src.core.workflow_provider.models.ClaimsWorkflowInput).

    semantic (PBI-14-03, default None): this turn's shared structured semantic interpretation
    (src.agents.shared.semantic_interpreter, the same repurposed per-turn LLM call this Agent
    already made). Deterministic extract_fields() always runs first and always wins; semantic
    entities only fill a field extract_fields left empty, and only above
    src.agents.shared.semantic_merge.MIN_CONFIDENCE_TO_APPLY. The pre-registration confirmation
    question additionally consults semantic.confirmation when the deterministic word-set fast
    path in src.agents.shared.confirmation is inconclusive."""
    if state.status == ClaimsIntakeStatus.SELECTING_POLICY:
        selection = resolve_selection(message, state.candidates)
        if selection is not None:
            state = state.model_copy(
                update={
                    "policy_number": selection.policy_number,
                    "line_of_business": selection.line_of_business,
                    "candidates": [],
                    "status": ClaimsIntakeStatus.COLLECTING_INFORMATION,
                }
            )
    current_state = extract_fields(message, state)
    if semantic is not None:
        current_state, _ = apply_semantic_entities(
            current_state,
            semantic.entities,
            semantic.intent_confidence,
            fields=_SEMANTIC_FALLBACK_FIELDS,
        )
    if state.last_asked_field == "confirmed" and current_state.confirmed is None:
        resolved_confirmation = resolve_confirmation(
            message,
            semantic_confirmation=semantic.confirmation if semantic is not None else None,
        )
        if resolved_confirmation is not None:
            current_state = current_state.model_copy(update={"confirmed": resolved_confirmation})
    tool_context: _ToolContext = {
        "correlation_id": correlation_id,
        "conversation_id": conversation_id,
        "user_id": user_id,
    }
    notices: list[str] = []

    while True:
        if (
            workflow_provider is not None
            and current_state.status == ClaimsIntakeStatus.READY_TO_REGISTER
        ):
            current_state, new_notices, should_continue = await _handle_ready_to_register_workflow(
                current_state, workflow_provider, tool_context, language
            )
        else:
            handler = _HANDLERS[current_state.status]
            current_state, new_notices, should_continue = await handler(
                current_state, tool_provider, tool_context, language
            )
        notices.extend(new_notices)
        if not should_continue:
            break

    return current_state, notices


async def _handle_new(
    state: ClaimsIntakeState, _tool_provider: ToolProvider, _ctx: _ToolContext, _language: Language
) -> _HandlerResult:
    return state.model_copy(update={"status": ClaimsIntakeStatus.COLLECTING_INFORMATION}), [], True


async def _handle_collecting_information(
    state: ClaimsIntakeState, tool_provider: ToolProvider, ctx: _ToolContext, language: Language
) -> _HandlerResult:
    # Customer discovery is a priority step, not just another required field: the caller's
    # name is asked for first, and looked up immediately once given — before any incident
    # detail — so a multi-policy caller is asked to pick a policy right away rather than after
    # narrating the whole incident. A direct policy number (regex-detected anywhere, any turn)
    # always short-circuits this entirely.
    if state.policy_number is None and state.customer_name is None:
        prompt = t(FIELD_PROMPTS, "customer_name", language)
        if not state.opening_acknowledged:
            # Conversational Policy (PBI-05-01): acknowledge what the caller already said
            # before asking anything — with empathy and the loss type if it was already
            # volunteered ("Se inundó mi casa." -> loss_type already known), or a short "Claro."
            # lead-in otherwise. Said exactly once per conversation.
            prompt = f"{opening_acknowledgment(loss_type=state.loss_type, language=language)} {prompt}"
        new_state = state.model_copy(
            update={"last_asked_field": "customer_name", "opening_acknowledged": True}
        )
        return new_state, [prompt], False

    if state.policy_number is None and state.customer_name is not None:
        new_state = state.model_copy(
            update={"status": ClaimsIntakeStatus.LOOKING_UP_CUSTOMER, "last_asked_field": None}
        )
        return new_state, [], True

    # PBI-05-01 requirement 9: once a policy is known (via customer discovery or a direct
    # policy number), resolve its authoritative line_of_business — silently, from the Tool
    # result, never guessed from conversation text — before asking any further incident
    # details, so the very next question is already profile-aware (Auto vs Property).
    # Customer-discovery paths already set this from the selected PolicyCandidate; only a
    # direct policy number needs this extra (cheap, synthetic, in-memory) lookup.
    if state.line_of_business is None:
        policy_result = await tool_provider.execute(
            ToolRequest(
                tool_name="policy_lookup", tool_input={"policy_number": state.policy_number}, **ctx
            )
        )
        if policy_result.success and policy_result.data is not None:
            state = state.model_copy(
                update={"line_of_business": policy_result.data.line_of_business}
            )
        # A failed lookup here is not reported — VALIDATING_POLICY's own policy_lookup call
        # will surface "policy not found" properly once the required fields are collected;
        # this step degrades to the LOB-agnostic common field set only, never blocks.

    group = next_question_group(state)
    if group:
        new_state = state.model_copy(
            update={"last_asked_field": group[0], "last_asked_group": group}
        )
        return new_state, [_prompt_for_group(group, language)], False

    new_state = state.model_copy(
        update={
            "status": ClaimsIntakeStatus.VALIDATING_POLICY,
            "last_asked_field": None,
            "last_asked_group": [],
        }
    )
    return new_state, [], True


def _prompt_for_group(group: list[str], language: Language) -> str:
    group_set = set(group)
    if group_set == _INCIDENT_DETAILS_GROUP:
        return t(_COMBINED_PROMPTS, "incident_details", language)
    if group_set == _YES_NO_GROUP:
        return t(_COMBINED_PROMPTS, "injuries_and_third_parties", language)
    return " ".join(t(FIELD_PROMPTS, field, language) for field in group)


async def _handle_looking_up_customer(
    state: ClaimsIntakeState, tool_provider: ToolProvider, ctx: _ToolContext, language: Language
) -> _HandlerResult:
    result = await tool_provider.execute(
        ToolRequest(
            tool_name="customer_lookup", tool_input={"full_name": state.customer_name}, **ctx
        )
    )
    if not result.success or result.data is None:
        notice = t(_MESSAGES, "customer_not_found", language, name=state.customer_name)
        new_state = state.model_copy(
            update={
                "customer_name": None,
                "status": ClaimsIntakeStatus.COLLECTING_INFORMATION,
                "last_asked_field": "customer_name",
            }
        )
        return new_state, [notice], False

    candidates = [
        PolicyCandidate(
            policy_number=policy.policy_number,
            customer_name=match.full_name,
            line_of_business=policy.line_of_business,
            vehicle_description=policy.vehicle_description,
        )
        for match in result.data.matches
        for policy in match.policies
    ]

    if len(candidates) == 1:
        only = candidates[0]
        detail = only.vehicle_description or only.property_description
        vehicle = f", {detail}" if detail else ""
        notice = t(
            _MESSAGES,
            "customer_single_match",
            language,
            line_of_business=only.line_of_business,
            vehicle=vehicle,
        )
        new_state = state.model_copy(
            update={
                "policy_number": only.policy_number,
                "line_of_business": only.line_of_business,
                "candidates": [],
                "status": ClaimsIntakeStatus.COLLECTING_INFORMATION,
            }
        )
        return new_state, [notice], True

    notice = t(
        _MESSAGES,
        "customer_multiple_matches",
        language,
        options=_format_candidates(candidates),
    )
    new_state = state.model_copy(
        update={"candidates": candidates, "status": ClaimsIntakeStatus.SELECTING_POLICY}
    )
    return new_state, [notice], False


def _format_candidates(candidates: list[PolicyCandidate]) -> str:
    ordinals_es = ["la primera", "la segunda", "la tercera", "la cuarta"]
    parts = []
    for index, candidate in enumerate(candidates):
        label = ordinals_es[index] if index < len(ordinals_es) else f"la #{index + 1}"
        detail = (
            candidate.vehicle_description
            or candidate.property_description
            or candidate.line_of_business
        )
        parts.append(f"{label} ({detail})")
    return "; ".join(parts) + "."


async def _handle_selecting_policy(
    state: ClaimsIntakeState, _tool_provider: ToolProvider, _ctx: _ToolContext, language: Language
) -> _HandlerResult:
    # Reached only if extract_fields/advance_claims_intake's own selection resolution (at the
    # top of advance_claims_intake) did not already resolve a candidate this turn.
    notice = t(
        _MESSAGES,
        "selection_not_understood",
        language,
        options=_format_candidates(state.candidates),
    )
    return state, [notice], False


async def _handle_validating_policy(
    state: ClaimsIntakeState, tool_provider: ToolProvider, ctx: _ToolContext, language: Language
) -> _HandlerResult:
    policy_result = await tool_provider.execute(
        ToolRequest(
            tool_name="policy_lookup", tool_input={"policy_number": state.policy_number}, **ctx
        )
    )
    if not policy_result.success or policy_result.data is None:
        notice = t(_MESSAGES, "policy_not_found", language, policy_number=state.policy_number)
        return state, [notice], False

    policy_active = policy_result.data.status == "active"

    payment_result = await tool_provider.execute(
        ToolRequest(
            tool_name="payment_status", tool_input={"policy_number": state.policy_number}, **ctx
        )
    )
    payment_current = (
        payment_result.data.payment_current
        if payment_result.success and payment_result.data is not None
        else None
    )

    coverage_result = await tool_provider.execute(
        ToolRequest(
            tool_name="coverage_lookup", tool_input={"policy_number": state.policy_number}, **ctx
        )
    )
    coverage_data = coverage_result.data if coverage_result.success else None

    notices: list[str] = []
    notices.append(t(_MESSAGES, "policy_active" if policy_active else "policy_inactive", language, status=policy_result.data.status))
    if payment_current is True:
        notices.append(t(_MESSAGES, "payment_current", language))
    elif payment_current is False:
        notices.append(t(_MESSAGES, "payment_issue", language))
    else:
        notices.append(t(_MESSAGES, "payment_unknown", language))

    if coverage_data is not None:
        notices.append(
            t(
                _MESSAGES,
                "coverage_found",
                language,
                coverage_type=coverage_data.coverage_type,
                limit=coverage_data.limit_amount,
                deductible=coverage_data.deductible,
            )
        )
    else:
        notices.append(t(_MESSAGES, "coverage_unknown", language))

    new_state = state.model_copy(
        update={
            "policy_validated": True,
            "policy_active": policy_active,
            "payment_current": payment_current,
            "holder_name": policy_result.data.holder_name,
            "line_of_business": policy_result.data.line_of_business,
            "coverage_type": coverage_data.coverage_type if coverage_data else None,
            "coverage_limit": coverage_data.limit_amount if coverage_data else None,
            "coverage_deductible": coverage_data.deductible if coverage_data else None,
            "status": ClaimsIntakeStatus.CONFIRMING,
        }
    )
    return new_state, notices, True


def _confirmation_lob_detail(state: ClaimsIntakeState, language: Language) -> str:
    if state.line_of_business == "auto" and state.vehicle_drivable is not None:
        key = (
            "confirmation_detail_vehicle_drivable"
            if state.vehicle_drivable
            else "confirmation_detail_vehicle_not_drivable"
        )
        return t(_MESSAGES, key, language)
    if state.line_of_business == "property" and state.property_habitable is not None:
        key = (
            "confirmation_detail_habitable"
            if state.property_habitable
            else "confirmation_detail_not_habitable"
        )
        return t(_MESSAGES, key, language)
    return ""


async def _handle_confirming(
    state: ClaimsIntakeState, _tool_provider: ToolProvider, _ctx: _ToolContext, language: Language
) -> _HandlerResult:
    if state.confirmed is None:
        notice = t(
            _MESSAGES,
            "confirmation_summary",
            language,
            policy_number=state.policy_number,
            event_date=state.event_date,
            event_location=state.event_location,
            loss_type=state.loss_type,
            lob_detail=_confirmation_lob_detail(state, language),
        )
        new_state = state.model_copy(update={"last_asked_field": "confirmed"})
        return new_state, [notice], False

    if state.confirmed:
        new_state = state.model_copy(update={"status": ClaimsIntakeStatus.READY_TO_REGISTER})
        return new_state, [], True

    # A decline must actually change something, or the very next turn would immediately
    # re-reach CONFIRMING with the same unchanged summary (missing_required_fields() would
    # return [] since every field is already filled, silently looping the caller back to the
    # same confirmation instead of letting them correct anything). Clearing the incident-detail
    # fields — never customer_name/policy_number/holder_name/coverage, already resolved — means
    # the grouped re-ask flow in _handle_collecting_information genuinely re-collects them.
    notice = t(_MESSAGES, "confirmation_declined", language)
    new_state = state.model_copy(
        update={
            "confirmed": None,
            "event_date": None,
            "event_time": None,
            "event_location": None,
            "loss_type": None,
            "loss_description": None,
            "contact_phone": None,
            "injuries_reported": None,
            "third_parties_involved": None,
            "vehicle_drivable": None,
            "property_habitable": None,
            "status": ClaimsIntakeStatus.COLLECTING_INFORMATION,
            "last_asked_field": None,
        }
    )
    return new_state, [notice], False


async def _handle_ready_to_register(
    state: ClaimsIntakeState, tool_provider: ToolProvider, ctx: _ToolContext, language: Language
) -> _HandlerResult:
    """Default (CLAIMS_WORKFLOW_PROVIDER=inprocess) path: registers the claim as a plain
    in-process Tool call. See _handle_ready_to_register_workflow for the WorkflowProvider path,
    used instead of this handler (and _handle_registered) when a workflow_provider is supplied
    to advance_claims_intake."""
    contact_name = state.customer_name or state.holder_name or t(_MESSAGES, "customer_default_name", language)
    result = await tool_provider.execute(
        ToolRequest(
            tool_name="claim_registration",
            tool_input={
                "policy_number": state.policy_number,
                "event_date": state.event_date,
                "event_time": state.event_time,
                "event_location": state.event_location,
                "loss_type": state.loss_type,
                "loss_description": state.loss_description,
                "contact_name": contact_name,
                "contact_phone": state.contact_phone,
                "contact_email": state.contact_email,
                "injuries_reported": bool(state.injuries_reported),
                "third_parties_involved": bool(state.third_parties_involved),
            },
            **ctx,
        )
    )
    if not result.success or result.data is None:
        notice = t(_MESSAGES, "registration_failed", language)
        return state, [notice], False

    new_state = state.model_copy(
        update={
            "claim_reference": result.data.claim_reference,
            "status": ClaimsIntakeStatus.REGISTERED,
        }
    )
    notice = t(_MESSAGES, "registration_success", language, claim_reference=result.data.claim_reference)
    return new_state, [notice], True


async def _handle_registered(
    state: ClaimsIntakeState, tool_provider: ToolProvider, ctx: _ToolContext, language: Language
) -> _HandlerResult:
    result = await tool_provider.execute(
        ToolRequest(
            tool_name="adjuster_assignment", tool_input={"claim_reference": state.claim_reference}, **ctx
        )
    )
    if not result.success or result.data is None:
        notice = t(_MESSAGES, "adjuster_pending", language, claim_reference=state.claim_reference)
        return state, [notice], False

    new_state = state.model_copy(
        update={
            "adjuster_assigned": result.data.adjuster_name,
            "status": ClaimsIntakeStatus.ADJUSTER_ASSIGNED,
        }
    )
    notice = t(
        _MESSAGES,
        "adjuster_assigned",
        language,
        adjuster_name=result.data.adjuster_name,
        claim_reference=state.claim_reference,
    )
    return new_state, [notice], False


async def _handle_adjuster_assigned(
    state: ClaimsIntakeState, _tool_provider: ToolProvider, _ctx: _ToolContext, language: Language
) -> _HandlerResult:
    notice = t(
        _MESSAGES,
        "already_assigned",
        language,
        claim_reference=state.claim_reference,
        adjuster_name=state.adjuster_assigned,
    )
    return state, [notice], False


async def _handle_ready_to_register_workflow(
    state: ClaimsIntakeState,
    workflow_provider: ClaimsWorkflowProvider,
    ctx: _ToolContext,
    language: Language,
) -> _HandlerResult:
    """CLAIMS_WORKFLOW_PROVIDER=durable (or any other ClaimsWorkflowProvider) path: registers
    the claim and assigns an adjuster as a single ClaimsWorkflowProvider.run() call, replacing
    what _handle_ready_to_register + _handle_registered do across two dict-dispatched statuses
    in the default in-process path. Produces the exact same notice text/ordering
    (registration_success, then adjuster_assigned or adjuster_pending) so the two
    CLAIMS_WORKFLOW_PROVIDER modes are conversationally indistinguishable to the caller."""
    contact_name = state.customer_name or state.holder_name or t(_MESSAGES, "customer_default_name", language)
    result = await workflow_provider.run(
        ClaimsWorkflowInput(
            correlation_id=ctx["correlation_id"],
            conversation_id=ctx["conversation_id"],
            user_id=ctx["user_id"],
            policy_number=state.policy_number or "",
            event_date=state.event_date,
            event_time=state.event_time,
            event_location=state.event_location,
            loss_type=state.loss_type,
            loss_description=state.loss_description,
            contact_name=contact_name,
            contact_phone=state.contact_phone,
            contact_email=state.contact_email,
            injuries_reported=bool(state.injuries_reported),
            third_parties_involved=bool(state.third_parties_involved),
        )
    )
    if not result.success or result.claim_reference is None:
        notice = t(_MESSAGES, "registration_failed", language)
        return state, [notice], False

    notices = [t(_MESSAGES, "registration_success", language, claim_reference=result.claim_reference)]
    if result.adjuster_name:
        new_state = state.model_copy(
            update={
                "claim_reference": result.claim_reference,
                "adjuster_assigned": result.adjuster_name,
                "status": ClaimsIntakeStatus.ADJUSTER_ASSIGNED,
            }
        )
        notices.append(
            t(
                _MESSAGES,
                "adjuster_assigned",
                language,
                adjuster_name=result.adjuster_name,
                claim_reference=result.claim_reference,
            )
        )
        return new_state, notices, False

    new_state = state.model_copy(
        update={"claim_reference": result.claim_reference, "status": ClaimsIntakeStatus.REGISTERED}
    )
    notices.append(t(_MESSAGES, "adjuster_pending", language, claim_reference=result.claim_reference))
    return new_state, notices, False


_HANDLERS: dict[ClaimsIntakeStatus, _Handler] = {
    ClaimsIntakeStatus.NEW: _handle_new,
    ClaimsIntakeStatus.COLLECTING_INFORMATION: _handle_collecting_information,
    ClaimsIntakeStatus.LOOKING_UP_CUSTOMER: _handle_looking_up_customer,
    ClaimsIntakeStatus.SELECTING_POLICY: _handle_selecting_policy,
    ClaimsIntakeStatus.VALIDATING_POLICY: _handle_validating_policy,
    ClaimsIntakeStatus.CONFIRMING: _handle_confirming,
    ClaimsIntakeStatus.READY_TO_REGISTER: _handle_ready_to_register,
    ClaimsIntakeStatus.REGISTERED: _handle_registered,
    ClaimsIntakeStatus.ADJUSTER_ASSIGNED: _handle_adjuster_assigned,
}

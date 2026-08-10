"""Claims Tool Layer + Claims Workflow — Azure Functions / Durable Functions (PBI-06-01).

Resolves Architecture Review Finding A-03 (CLAUDE.md §4.2/§4.1: "Azure Functions as the Tool
Layer", "Durable Functions as the Workflow Engine"). See
docs/Architecture/adr/0003-azure-functions-tool-and-workflow-layer.md for the full decision.

Two responsibilities, both deterministic, both with NO LLM and NO conversational logic
(CLAUDE.md §4.2 "Functions are responsible ONLY for deterministic business actions"):

1. Tool Layer (HTTP): POST /api/tools/{tool_name} executes one registered Claims Tool and
   returns its ToolResult as JSON — the exact same contract src.tools.executor.ToolExecutor
   already returns in-process. Called by src.core.tool_provider.azure_function.
   AzureFunctionToolProvider when TOOL_PROVIDER=azure_functions.

2. Workflow Engine (Durable Functions): claims_workflow_orchestrator runs
   policy_lookup -> payment_status -> coverage_lookup -> claim_registration ->
   adjuster_assignment as one durable transaction, started via the HTTP starter route
   /api/orchestrators/claims_workflow_orchestrator. Called by
   src.core.workflow_provider.durable.DurableClaimsWorkflowProvider when
   CLAIMS_WORKFLOW_PROVIDER=durable. Holds no conversational state — ClaimsAgent
   (src.agents.claims.workflow) still owns 100% of the conversation and starts this workflow
   only after the caller has confirmed.

No business logic is duplicated here: every Tool call below goes through the same
src.tools.executor.ToolExecutor / src.services.tools.* classes the in-process path already
uses (vendored into this deployment package at build time — see build.ps1 — mirroring
apps/api/Dockerfile's own repo-root src/ COPY convention, CLAUDE.md §6 "single reusable src/
library").
"""

from __future__ import annotations

import logging
from typing import Any

import azure.durable_functions as df
import azure.functions as func

from src.services.tools.adjuster_assignment_tool import AdjusterAssignmentTool
from src.services.tools.claim_registration_tool import ClaimRegistrationTool
from src.services.tools.coverage_lookup_tool import CoverageLookupTool
from src.services.tools.payment_status_tool import PaymentStatusTool
from src.services.tools.policy_lookup_tool import PolicyLookupTool
from src.tools.executor import ToolExecutor
from src.tools.models import ToolRequest
from src.tools.registry import InMemoryToolRegistry

logger = logging.getLogger(__name__)

# ANONYMOUS (DEV/academic scope, documented in ADR-0003): a Consumption-plan Function App's
# runtime keys are only generated after code has synced, which cannot happen inside the same
# Bicep deployment that creates the app — key-based auth would require a fragile post-deploy
# manual step. src.core.tool_provider.azure_function.AzureFunctionToolProvider /
# src.core.workflow_provider.durable.DurableClaimsWorkflowProvider already support key auth
# (TOOL_PROVIDER_/DURABLE_FUNCTIONS_USE_KEY) for when a future PBI wires it (e.g. via Easy Auth
# or APIM + Managed Identity) — this Function App itself is network-reachable only via HTTPS to
# its own *.azurewebsites.net hostname, not exposed through any other shared ingress.
app = df.DFApp(http_auth_level=func.AuthLevel.ANONYMOUS)


def _build_tool_executor() -> ToolExecutor:
    """Registers exactly the Claims Tools this Function App is authorized to execute — the
    Claims Agent's approved Tool set (CLAUDE.md §2), not the full 14-Tool platform registry.
    Built once per cold start, mirroring apps/api/src/api/dependencies.get_tool_registry's own
    process-wide singleton pattern.
    """
    registry = InMemoryToolRegistry()
    registry.register(PolicyLookupTool())  # mandatory (PBI-06-01 Phase 3)
    registry.register(PaymentStatusTool())  # mandatory
    registry.register(CoverageLookupTool())  # mandatory
    registry.register(ClaimRegistrationTool())  # stretch, low-risk to include
    registry.register(AdjusterAssignmentTool())  # stretch, low-risk to include
    return ToolExecutor(tool_registry=registry)


_tool_executor = _build_tool_executor()


# --- Tool Layer (HTTP) --------------------------------------------------------------------


@app.route(route="tools/{tool_name}", methods=["POST"])
async def tools_http(req: func.HttpRequest) -> func.HttpResponse:
    """Executes one Claims Tool by name. Request/response bodies mirror ToolRequest/ToolResult
    exactly (src.tools.models) — this handler adds no business logic, only HTTP<->Tool
    transport, and normalizes every failure into a JSON body, never an unhandled 5xx stack
    trace (CLAUDE.md §11 safe-response guarantee)."""
    tool_name = req.route_params.get("tool_name", "")
    correlation_id = req.headers.get("X-Correlation-ID")

    try:
        body: dict[str, Any] = req.get_json()
    except ValueError:
        logger.warning(
            "claims_tool_invalid_request_body",
            extra={"tool_name": tool_name, "correlation_id": correlation_id},
        )
        return func.HttpResponse(
            body='{"error": "Request body must be valid JSON"}',
            status_code=400,
            mimetype="application/json",
        )

    request = ToolRequest(
        tool_name=tool_name,
        tool_input=body.get("tool_input", {}),
        correlation_id=body.get("correlation_id") or correlation_id,
        conversation_id=body.get("conversation_id"),
        user_id=body.get("user_id"),
    )

    logger.info(
        "claims_tool_activity_start",
        extra={"tool_name": tool_name, "correlation_id": request.correlation_id},
    )
    result = await _tool_executor.execute(request)
    logger.info(
        "claims_tool_activity_end",
        extra={
            "tool_name": tool_name,
            "correlation_id": request.correlation_id,
            "success": result.success,
        },
    )

    return func.HttpResponse(
        body=result.model_dump_json(),
        status_code=200,
        mimetype="application/json",
    )


# --- Workflow Engine (Durable Functions) --------------------------------------------------


@app.route(route="orchestrators/claims_workflow_orchestrator", methods=["POST"])
@app.durable_client_input(client_name="client")
async def claims_workflow_starter(
    req: func.HttpRequest, client: df.DurableOrchestrationClient
) -> func.HttpResponse:
    """Starts one claims_workflow_orchestrator run. The request body is the full
    ClaimsWorkflowInput JSON payload (src.core.workflow_provider.models) — passed through
    unmodified as the orchestration's input, never inspected or altered here."""
    body = req.get_json()
    correlation_id = body.get("correlation_id") or req.headers.get("X-Correlation-ID")
    logger.info(
        "claims_workflow_start",
        extra={"correlation_id": correlation_id, "policy_number": body.get("policy_number")},
    )
    instance_id = await client.start_new("claims_workflow_orchestrator", client_input=body)
    return client.create_check_status_response(req, instance_id)


@app.orchestration_trigger(context_name="context")
def claims_workflow_orchestrator(context: df.DurableOrchestrationContext):
    """Orchestrates the Claims post-confirmation transaction — the exact flow PBI-06-01
    specifies: policy_lookup -> payment_status -> coverage_lookup -> claim_registration ->
    adjuster_assignment -> return result. Deterministic-replay-safe: every side effect
    (including the correlation_id-carrying log lines) lives inside an activity, never directly
    in this generator, per the Durable Functions orchestrator constraints."""
    workflow_input: dict[str, Any] = context.get_input()
    correlation_id = workflow_input.get("correlation_id")
    ctx = {
        "correlation_id": correlation_id,
        "conversation_id": workflow_input.get("conversation_id"),
        "user_id": workflow_input.get("user_id"),
    }

    policy_result = yield context.call_activity(
        "policy_lookup_activity",
        {"tool_input": {"policy_number": workflow_input["policy_number"]}, **ctx},
    )
    if not policy_result["success"]:
        return {"success": False, "error": policy_result.get("error")}

    # Payment/coverage are re-validated as part of the durable transaction (PBI-06-01's stated
    # flow) but, matching CLAUDE.md §2 (Claims Agent never blocks on payment/coverage issues),
    # neither failure stops registration — same "surface as a fact, never block" rule the
    # in-process VALIDATING_POLICY handler already applies.
    yield context.call_activity(
        "payment_status_activity",
        {"tool_input": {"policy_number": workflow_input["policy_number"]}, **ctx},
    )
    yield context.call_activity(
        "coverage_lookup_activity",
        {"tool_input": {"policy_number": workflow_input["policy_number"]}, **ctx},
    )

    registration_result = yield context.call_activity(
        "claim_registration_activity",
        {
            "tool_input": {
                "policy_number": workflow_input["policy_number"],
                "event_date": workflow_input.get("event_date"),
                "event_time": workflow_input.get("event_time"),
                "event_location": workflow_input.get("event_location"),
                "loss_type": workflow_input.get("loss_type"),
                "loss_description": workflow_input.get("loss_description"),
                "contact_name": workflow_input["contact_name"],
                "contact_phone": workflow_input.get("contact_phone"),
                "contact_email": workflow_input.get("contact_email"),
                "injuries_reported": bool(workflow_input.get("injuries_reported")),
                "third_parties_involved": bool(workflow_input.get("third_parties_involved")),
            },
            **ctx,
        },
    )
    if not registration_result["success"]:
        return {"success": False, "error": registration_result.get("error")}

    claim_reference = registration_result["data"]["claim_reference"]

    assignment_result = yield context.call_activity(
        "adjuster_assignment_activity",
        {"tool_input": {"claim_reference": claim_reference}, **ctx},
    )
    adjuster_name = (
        assignment_result["data"]["adjuster_name"] if assignment_result["success"] else None
    )

    return {"success": True, "claim_reference": claim_reference, "adjuster_name": adjuster_name}


def _activity_context(payload: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    return payload.get("tool_input", {}), payload.get("correlation_id")


@app.activity_trigger(input_name="payload")
async def policy_lookup_activity(payload: dict[str, Any]) -> dict[str, Any]:
    tool_input, correlation_id = _activity_context(payload)
    logger.info("claims_activity_start", extra={"activity": "policy_lookup", "correlation_id": correlation_id})
    result = await _tool_executor.execute(
        ToolRequest(tool_name="policy_lookup", tool_input=tool_input, correlation_id=correlation_id)
    )
    logger.info("claims_activity_end", extra={"activity": "policy_lookup", "correlation_id": correlation_id, "success": result.success})
    return result.model_dump(mode="json")


@app.activity_trigger(input_name="payload")
async def payment_status_activity(payload: dict[str, Any]) -> dict[str, Any]:
    tool_input, correlation_id = _activity_context(payload)
    logger.info("claims_activity_start", extra={"activity": "payment_status", "correlation_id": correlation_id})
    result = await _tool_executor.execute(
        ToolRequest(tool_name="payment_status", tool_input=tool_input, correlation_id=correlation_id)
    )
    logger.info("claims_activity_end", extra={"activity": "payment_status", "correlation_id": correlation_id, "success": result.success})
    return result.model_dump(mode="json")


@app.activity_trigger(input_name="payload")
async def coverage_lookup_activity(payload: dict[str, Any]) -> dict[str, Any]:
    tool_input, correlation_id = _activity_context(payload)
    logger.info("claims_activity_start", extra={"activity": "coverage_lookup", "correlation_id": correlation_id})
    result = await _tool_executor.execute(
        ToolRequest(tool_name="coverage_lookup", tool_input=tool_input, correlation_id=correlation_id)
    )
    logger.info("claims_activity_end", extra={"activity": "coverage_lookup", "correlation_id": correlation_id, "success": result.success})
    return result.model_dump(mode="json")


@app.activity_trigger(input_name="payload")
async def claim_registration_activity(payload: dict[str, Any]) -> dict[str, Any]:
    tool_input, correlation_id = _activity_context(payload)
    logger.info("claims_activity_start", extra={"activity": "claim_registration", "correlation_id": correlation_id})
    result = await _tool_executor.execute(
        ToolRequest(tool_name="claim_registration", tool_input=tool_input, correlation_id=correlation_id)
    )
    logger.info(
        "claims_activity_end",
        extra={
            "activity": "claim_registration",
            "correlation_id": correlation_id,
            "success": result.success,
            "claim_reference": result.data.claim_reference if result.success and result.data else None,
        },
    )
    return result.model_dump(mode="json")


@app.activity_trigger(input_name="payload")
async def adjuster_assignment_activity(payload: dict[str, Any]) -> dict[str, Any]:
    tool_input, correlation_id = _activity_context(payload)
    logger.info("claims_activity_start", extra={"activity": "adjuster_assignment", "correlation_id": correlation_id})
    result = await _tool_executor.execute(
        ToolRequest(tool_name="adjuster_assignment", tool_input=tool_input, correlation_id=correlation_id)
    )
    logger.info("claims_activity_end", extra={"activity": "adjuster_assignment", "correlation_id": correlation_id, "success": result.success})
    return result.model_dump(mode="json")

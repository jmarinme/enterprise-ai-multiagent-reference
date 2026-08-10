"""DurableClaimsWorkflowProvider — executes the Claims post-confirmation transaction as a
Durable Functions orchestration (ops/functions/claims_tools/function_app.py:
claims_workflow_orchestrator), aligning the Workflow Engine with CLAUDE.md §4.1/§5
(PBI-06-01, resolves Architecture Review Finding A-03).

Flow (orchestrated entirely inside the Durable Functions host, never here):
    policy_lookup -> payment_status -> coverage_lookup -> claim_registration ->
    adjuster_assignment -> return result

This provider only starts the orchestration via its HTTP starter endpoint and polls the Durable
Functions status endpoint until it completes — it holds no workflow logic and no conversational
state (CLAUDE.md §4.1: "Do NOT move conversational state into Durable Functions" — ClaimsAgent's
state machine is untouched by this class).

Every failure mode (timeout, connection error, non-2xx, orchestration Failed/Terminated) is
normalized into ClaimsWorkflowResult(success=False, error=...) — this provider never raises to
its caller, matching InProcessClaimsWorkflowProvider's own contract.

Only imported when CLAIMS_WORKFLOW_PROVIDER=durable (src.core.workflow_provider.factory), so
aiohttp is never required for the default in-process configuration.
"""

from __future__ import annotations

import asyncio
import logging

import aiohttp

from src.core.workflow_provider.models import ClaimsWorkflowInput, ClaimsWorkflowResult
from src.domain.secret_provider import SecretProvider

logger = logging.getLogger(__name__)

_TERMINAL_FAILURE_STATUSES = {"Failed", "Terminated"}


class DurableClaimsWorkflowProvider:
    """ClaimsWorkflowProvider backend that starts and polls a Durable Functions orchestration."""

    def __init__(
        self,
        base_url: str,
        orchestrator_name: str = "claims_workflow_orchestrator",
        poll_interval_seconds: float = 1.0,
        timeout_seconds: float = 60.0,
        secret_provider: SecretProvider | None = None,
        function_key_secret_name: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._orchestrator_name = orchestrator_name
        self._poll_interval_seconds = poll_interval_seconds
        self._timeout_seconds = timeout_seconds
        self._secret_provider = secret_provider
        self._function_key_secret_name = function_key_secret_name
        self._function_key: str | None = None
        self._function_key_resolved = False

    async def run(self, workflow_input: ClaimsWorkflowInput) -> ClaimsWorkflowResult:
        try:
            function_key = await self._resolve_function_key()
        except Exception as exc:  # noqa: BLE001 — secret resolution must degrade to a result
            logger.warning("durable_workflow_key_error", extra={"error": str(exc)})
            return ClaimsWorkflowResult(
                success=False, error=f"Could not resolve Azure Function key: {exc}"
            )

        headers = {"Content-Type": "application/json"}
        if workflow_input.correlation_id:
            headers["X-Correlation-ID"] = workflow_input.correlation_id
        params = {"code": function_key} if function_key else None
        start_url = f"{self._base_url}/api/orchestrators/{self._orchestrator_name}"
        timeout = aiohttp.ClientTimeout(total=self._timeout_seconds)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    start_url,
                    json=workflow_input.model_dump(),
                    headers=headers,
                    params=params,
                ) as response:
                    if response.status >= 400:
                        text = await response.text()
                        return ClaimsWorkflowResult(
                            success=False,
                            error=f"Failed to start Durable workflow (HTTP {response.status}): {text}",
                        )
                    start_body = await response.json(content_type=None)

                status_query_uri = start_body.get("statusQueryGetUri")
                if not status_query_uri:
                    return ClaimsWorkflowResult(
                        success=False,
                        error="Durable Functions starter response missing statusQueryGetUri",
                    )

                return await self._poll_until_complete(session, status_query_uri)
        except TimeoutError:
            logger.warning(
                "durable_workflow_timeout", extra={"correlation_id": workflow_input.correlation_id}
            )
            return ClaimsWorkflowResult(success=False, error="Durable workflow call timed out")
        except (aiohttp.ClientError, ValueError) as exc:
            logger.warning(
                "durable_workflow_error",
                extra={"correlation_id": workflow_input.correlation_id, "error": str(exc)},
            )
            return ClaimsWorkflowResult(success=False, error=f"Durable workflow call failed: {exc}")

    async def _poll_until_complete(
        self, session: aiohttp.ClientSession, status_query_uri: str
    ) -> ClaimsWorkflowResult:
        elapsed = 0.0
        while elapsed < self._timeout_seconds:
            async with session.get(status_query_uri) as response:
                body = await response.json(content_type=None)
            runtime_status = body.get("runtimeStatus")

            if runtime_status == "Completed":
                output = body.get("output") or {}
                return ClaimsWorkflowResult(
                    success=bool(output.get("success", True)),
                    claim_reference=output.get("claim_reference"),
                    adjuster_name=output.get("adjuster_name"),
                    error=output.get("error"),
                )
            if runtime_status in _TERMINAL_FAILURE_STATUSES:
                return ClaimsWorkflowResult(
                    success=False,
                    error=f"Durable workflow ended with status '{runtime_status}'",
                )

            await asyncio.sleep(self._poll_interval_seconds)
            elapsed += self._poll_interval_seconds

        return ClaimsWorkflowResult(success=False, error="Durable workflow polling timed out")

    async def _resolve_function_key(self) -> str | None:
        if self._function_key_resolved:
            return self._function_key
        if self._secret_provider is not None and self._function_key_secret_name is not None:
            self._function_key = await self._secret_provider.get_secret(
                self._function_key_secret_name
            )
        self._function_key_resolved = True
        return self._function_key

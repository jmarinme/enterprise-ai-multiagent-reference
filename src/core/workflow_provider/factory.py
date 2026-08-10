"""Selects and configures the ClaimsWorkflowProvider implementation from
ClaimsWorkflowSettings — same factory pattern as src.core.tool_provider.factory.
"""

from __future__ import annotations

from src.config.settings import ClaimsWorkflowSettings
from src.core.tool_provider.protocol import ToolProvider
from src.core.workflow_provider.in_process import InProcessClaimsWorkflowProvider
from src.core.workflow_provider.protocol import ClaimsWorkflowProvider
from src.domain.secret_provider import SecretProvider


def get_claims_workflow_provider(
    settings: ClaimsWorkflowSettings,
    tool_provider: ToolProvider,
    secret_provider: SecretProvider | None = None,
) -> ClaimsWorkflowProvider:
    """Return the ClaimsWorkflowProvider implementation selected by settings.

    Defaults to InProcessClaimsWorkflowProvider (CLAIMS_WORKFLOW_PROVIDER=inprocess) so local
    development and tests never require Durable Functions connectivity — same default-safe
    pattern as every other provider factory in this codebase.
    """
    if settings.claims_workflow_provider == "durable":
        from src.core.workflow_provider.durable import DurableClaimsWorkflowProvider

        if not settings.durable_functions_base_url:
            raise ValueError(
                "DURABLE_FUNCTIONS_BASE_URL is required when CLAIMS_WORKFLOW_PROVIDER=durable"
            )
        return DurableClaimsWorkflowProvider(
            base_url=settings.durable_functions_base_url,
            poll_interval_seconds=settings.durable_functions_poll_interval_seconds,
            timeout_seconds=settings.durable_functions_timeout_seconds,
            secret_provider=secret_provider if settings.durable_functions_use_key else None,
            function_key_secret_name=(
                settings.durable_functions_key_secret_name
                if settings.durable_functions_use_key
                else None
            ),
        )

    return InProcessClaimsWorkflowProvider(tool_provider=tool_provider)

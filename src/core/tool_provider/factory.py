"""Selects and configures the ToolProvider implementation from ToolProviderSettings — same
factory pattern as src.llm.factory / src.rag.factory / src.services.conversation_store.factory.
"""

from __future__ import annotations

from src.config.settings import ToolProviderSettings
from src.core.tool_provider.in_process import InProcessToolProvider
from src.core.tool_provider.protocol import ToolProvider
from src.domain.secret_provider import SecretProvider
from src.tools.executor import ToolExecutor


def get_tool_provider(
    settings: ToolProviderSettings,
    tool_executor: ToolExecutor,
    secret_provider: SecretProvider | None = None,
) -> ToolProvider:
    """Return the ToolProvider implementation selected by settings.

    Defaults to InProcessToolProvider (TOOL_PROVIDER=inprocess) so local development and tests
    never require Azure Functions connectivity — same default-safe pattern as every other
    provider factory in this codebase.
    """
    if settings.tool_provider == "azure_functions":
        from src.core.tool_provider.azure_function import AzureFunctionToolProvider

        if not settings.azure_functions_base_url:
            raise ValueError(
                "AZURE_FUNCTIONS_BASE_URL is required when TOOL_PROVIDER=azure_functions"
            )
        return AzureFunctionToolProvider(
            base_url=settings.azure_functions_base_url,
            timeout_seconds=settings.azure_functions_timeout_seconds,
            secret_provider=secret_provider if settings.azure_functions_use_key else None,
            function_key_secret_name=(
                settings.azure_functions_key_secret_name
                if settings.azure_functions_use_key
                else None
            ),
        )

    return InProcessToolProvider(tool_executor=tool_executor)

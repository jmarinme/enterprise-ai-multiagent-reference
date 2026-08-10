"""Unit tests for src.core.tool_provider.factory.get_tool_provider: provider selection from
settings, and that azure_functions mode requires a base URL."""

import pytest

from src.config.settings import ToolProviderSettings
from src.core.tool_provider.azure_function import AzureFunctionToolProvider
from src.core.tool_provider.factory import get_tool_provider
from src.core.tool_provider.in_process import InProcessToolProvider
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry


def _tool_executor() -> ToolExecutor:
    return ToolExecutor(tool_registry=InMemoryToolRegistry())


def test_defaults_to_in_process_provider() -> None:
    settings = ToolProviderSettings()

    provider = get_tool_provider(settings, tool_executor=_tool_executor())

    assert isinstance(provider, InProcessToolProvider)


def test_azure_functions_mode_builds_azure_function_provider() -> None:
    settings = ToolProviderSettings(
        tool_provider="azure_functions",
        azure_functions_base_url="https://func-tmxap-dev.azurewebsites.net",
    )

    provider = get_tool_provider(settings, tool_executor=_tool_executor())

    assert isinstance(provider, AzureFunctionToolProvider)


def test_azure_functions_mode_without_base_url_raises() -> None:
    settings = ToolProviderSettings(tool_provider="azure_functions")

    with pytest.raises(ValueError, match="AZURE_FUNCTIONS_BASE_URL"):
        get_tool_provider(settings, tool_executor=_tool_executor())

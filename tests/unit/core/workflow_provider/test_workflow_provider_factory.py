"""Unit tests for src.core.workflow_provider.factory.get_claims_workflow_provider: provider
selection from settings, and that durable mode requires a base URL."""

import pytest

from src.config.settings import ClaimsWorkflowSettings
from src.core.tool_provider.in_process import InProcessToolProvider
from src.core.workflow_provider.durable import DurableClaimsWorkflowProvider
from src.core.workflow_provider.factory import get_claims_workflow_provider
from src.core.workflow_provider.in_process import InProcessClaimsWorkflowProvider
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry


def _tool_provider() -> InProcessToolProvider:
    return InProcessToolProvider(tool_executor=ToolExecutor(tool_registry=InMemoryToolRegistry()))


def test_defaults_to_in_process_workflow_provider() -> None:
    settings = ClaimsWorkflowSettings()

    provider = get_claims_workflow_provider(settings, tool_provider=_tool_provider())

    assert isinstance(provider, InProcessClaimsWorkflowProvider)


def test_durable_mode_builds_durable_provider() -> None:
    settings = ClaimsWorkflowSettings(
        claims_workflow_provider="durable",
        durable_functions_base_url="https://func-tmxap-dev.azurewebsites.net",
    )

    provider = get_claims_workflow_provider(settings, tool_provider=_tool_provider())

    assert isinstance(provider, DurableClaimsWorkflowProvider)


def test_durable_mode_without_base_url_raises() -> None:
    settings = ClaimsWorkflowSettings(claims_workflow_provider="durable")

    with pytest.raises(ValueError, match="DURABLE_FUNCTIONS_BASE_URL"):
        get_claims_workflow_provider(settings, tool_provider=_tool_provider())

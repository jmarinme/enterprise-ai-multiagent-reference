"""Unit tests for InProcessToolProvider: it must delegate every call to the wrapped
ToolExecutor unchanged — no added logic, no altered contract."""

from pydantic import BaseModel

from src.core.tool_provider.in_process import InProcessToolProvider
from src.tools.executor import ToolExecutor
from src.tools.models import ToolExecutionContext, ToolRequest, ToolResult
from src.tools.registry import InMemoryToolRegistry


class _EchoInput(BaseModel):
    value: str


class _EchoOutput(BaseModel):
    echoed: str


class _EchoTool:
    name = "echo_tool"
    description = "Echoes input."
    version = "1.0.0"
    input_model = _EchoInput

    async def execute(
        self, tool_input: _EchoInput, context: ToolExecutionContext
    ) -> ToolResult[_EchoOutput]:
        return ToolResult(
            tool_name=self.name,
            success=True,
            data=_EchoOutput(echoed=tool_input.value),
            correlation_id=context.correlation_id,
        )


def _build_provider() -> InProcessToolProvider:
    registry = InMemoryToolRegistry()
    registry.register(_EchoTool())
    return InProcessToolProvider(tool_executor=ToolExecutor(tool_registry=registry))


async def test_in_process_provider_delegates_success_to_tool_executor() -> None:
    provider = _build_provider()

    result = await provider.execute(
        ToolRequest(tool_name="echo_tool", tool_input={"value": "hello"}, correlation_id="c-1")
    )

    assert result.success is True
    assert result.data is not None
    assert result.data.echoed == "hello"
    assert result.correlation_id == "c-1"


async def test_in_process_provider_delegates_failure_to_tool_executor() -> None:
    provider = _build_provider()

    result = await provider.execute(ToolRequest(tool_name="does_not_exist", tool_input={}))

    assert result.success is False
    assert result.error is not None
    assert "does_not_exist" in result.error

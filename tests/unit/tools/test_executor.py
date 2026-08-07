"""Unit tests for ToolExecutor: valid input execution, invalid input, execution failure,
ToolResult contract, context propagation, missing tool.
"""

from pydantic import BaseModel

from src.tools.executor import ToolExecutor
from src.tools.models import ToolExecutionContext, ToolRequest, ToolResult
from src.tools.registry import InMemoryToolRegistry


class _EchoInput(BaseModel):
    value: str


class _EchoOutput(BaseModel):
    echoed: str
    correlation_id: str | None
    conversation_id: str | None
    user_id: str | None


class _EchoTool:
    """Deterministic stub tool: echoes its input and the propagated context back."""

    name = "echo_tool"
    description = "Echoes input and context for executor tests."
    version = "1.0.0"
    input_model = _EchoInput

    async def execute(
        self, tool_input: _EchoInput, context: ToolExecutionContext
    ) -> ToolResult[_EchoOutput]:
        return ToolResult(
            tool_name=self.name,
            success=True,
            data=_EchoOutput(
                echoed=tool_input.value,
                correlation_id=context.correlation_id,
                conversation_id=context.conversation_id,
                user_id=context.user_id,
            ),
            correlation_id=context.correlation_id,
        )


class _ExplodingTool:
    """Deterministic stub tool that always raises, to test failure normalization."""

    name = "exploding_tool"
    description = "Always raises."
    version = "1.0.0"
    input_model = _EchoInput

    async def execute(
        self, tool_input: _EchoInput, context: ToolExecutionContext
    ) -> ToolResult[_EchoOutput]:
        raise RuntimeError("synthetic failure for testing")


def _build_executor() -> ToolExecutor:
    registry = InMemoryToolRegistry()
    registry.register(_EchoTool())
    registry.register(_ExplodingTool())
    return ToolExecutor(tool_registry=registry)


async def test_valid_input_executes_successfully_and_returns_typed_data() -> None:
    executor = _build_executor()

    result = await executor.execute(
        ToolRequest(tool_name="echo_tool", tool_input={"value": "hello"})
    )

    assert result.success is True
    assert result.tool_name == "echo_tool"
    assert result.error is None
    assert result.data is not None
    assert result.data.echoed == "hello"


async def test_context_is_propagated_to_the_tool() -> None:
    executor = _build_executor()

    result = await executor.execute(
        ToolRequest(
            tool_name="echo_tool",
            tool_input={"value": "hi"},
            correlation_id="corr-1",
            conversation_id="conv-1",
            user_id="user-1",
        )
    )

    assert result.data is not None
    assert result.data.correlation_id == "corr-1"
    assert result.data.conversation_id == "conv-1"
    assert result.data.user_id == "user-1"
    assert result.correlation_id == "corr-1"


async def test_invalid_input_returns_a_failed_tool_result_not_a_raised_exception() -> None:
    executor = _build_executor()

    result = await executor.execute(
        ToolRequest(tool_name="echo_tool", tool_input={"wrong_field": "oops"})
    )

    assert result.success is False
    assert result.data is None
    assert result.error is not None
    assert "echo_tool" in result.error


async def test_execution_failure_is_normalized_into_a_failed_tool_result() -> None:
    executor = _build_executor()

    result = await executor.execute(
        ToolRequest(tool_name="exploding_tool", tool_input={"value": "boom"})
    )

    assert result.success is False
    assert result.data is None
    assert result.error is not None
    assert "exploding_tool" in result.error
    assert "synthetic failure for testing" in result.error


async def test_missing_tool_returns_a_failed_tool_result_not_a_raised_exception() -> None:
    executor = _build_executor()

    result = await executor.execute(
        ToolRequest(tool_name="does_not_exist", tool_input={})
    )

    assert result.success is False
    assert result.tool_name == "does_not_exist"
    assert result.error is not None
    assert "does_not_exist" in result.error


async def test_tool_result_contract_always_includes_tool_name_and_success() -> None:
    executor = _build_executor()

    success_result = await executor.execute(
        ToolRequest(tool_name="echo_tool", tool_input={"value": "x"})
    )
    failure_result = await executor.execute(
        ToolRequest(tool_name="does_not_exist", tool_input={})
    )

    for result in (success_result, failure_result):
        assert isinstance(result, ToolResult)
        assert isinstance(result.tool_name, str)
        assert isinstance(result.success, bool)

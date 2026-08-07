"""Unit tests for InMemoryToolRegistry: register, unregister, resolve, list, duplicate
registration, missing tool.
"""

import pytest

from src.tools.exceptions import ToolAlreadyRegisteredError, ToolNotFoundError
from src.tools.models import ToolExecutionContext, ToolResult
from src.tools.registry import InMemoryToolRegistry


class _StubInput:
    """Minimal stand-in; only used to give the stub tool an input_model attribute."""


class _StubTool:
    def __init__(self, name: str = "stub_tool") -> None:
        self.name = name
        self.description = "Stub tool for registry tests."
        self.version = "1.0.0"
        self.input_model = _StubInput

    async def execute(self, tool_input: object, context: ToolExecutionContext) -> ToolResult:
        return ToolResult(tool_name=self.name, success=True)


def test_register_and_resolve_returns_the_registered_tool() -> None:
    registry = InMemoryToolRegistry()
    tool = _StubTool()

    registry.register(tool)

    assert registry.resolve("stub_tool") is tool


def test_resolve_raises_tool_not_found_error_when_unregistered() -> None:
    registry = InMemoryToolRegistry()

    with pytest.raises(ToolNotFoundError):
        registry.resolve("does_not_exist")


def test_register_raises_on_duplicate_name() -> None:
    registry = InMemoryToolRegistry()
    registry.register(_StubTool("dup_tool"))

    with pytest.raises(ToolAlreadyRegisteredError):
        registry.register(_StubTool("dup_tool"))


def test_unregister_removes_the_tool() -> None:
    registry = InMemoryToolRegistry()
    registry.register(_StubTool("stub_tool"))

    registry.unregister("stub_tool")

    with pytest.raises(ToolNotFoundError):
        registry.resolve("stub_tool")


def test_unregister_is_a_no_op_when_nothing_registered() -> None:
    registry = InMemoryToolRegistry()

    registry.unregister("does_not_exist")  # must not raise


def test_unregister_then_register_again_succeeds() -> None:
    registry = InMemoryToolRegistry()
    registry.register(_StubTool("stub_tool"))
    registry.unregister("stub_tool")

    registry.register(_StubTool("stub_tool"))  # must not raise ToolAlreadyRegisteredError

    assert registry.resolve("stub_tool") is not None


def test_list_returns_metadata_for_all_registered_tools() -> None:
    registry = InMemoryToolRegistry()
    registry.register(_StubTool("tool_a"))
    registry.register(_StubTool("tool_b"))

    metadata = registry.list()

    assert {m.name for m in metadata} == {"tool_a", "tool_b"}
    assert all(m.version == "1.0.0" for m in metadata)
    assert all(m.description for m in metadata)

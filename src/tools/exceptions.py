"""Typed exceptions for the Tool execution framework."""

from __future__ import annotations


class ToolError(Exception):
    """Base class for all Tool framework errors."""


class ToolNotFoundError(ToolError):
    """Raised when the ToolRegistry has no Tool registered under the requested name."""

    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        super().__init__(f"No tool registered with name '{tool_name}'")


class ToolAlreadyRegisteredError(ToolError):
    """Raised when register() is called with a name that is already registered."""

    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        super().__init__(f"A tool named '{tool_name}' is already registered")


class ToolValidationError(ToolError):
    """Raised when raw tool_input fails validation against the resolved Tool's input_model."""

    def __init__(self, tool_name: str, message: str) -> None:
        self.tool_name = tool_name
        self.message = message
        super().__init__(f"Invalid input for tool '{tool_name}': {message}")


class ToolExecutionError(ToolError):
    """Raised when a Tool's execute() raises while running."""

    def __init__(self, tool_name: str, message: str) -> None:
        self.tool_name = tool_name
        self.message = message
        super().__init__(f"Tool '{tool_name}' execution failed: {message}")

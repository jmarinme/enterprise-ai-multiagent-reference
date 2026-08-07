"""Typed exceptions for the Prompt Management framework."""

from __future__ import annotations


class PromptError(Exception):
    """Base class for all Prompt framework errors."""


class PromptNotFoundError(PromptError):
    """Raised when a logical identifier does not resolve to any stored prompt."""

    def __init__(self, identifier: str) -> None:
        self.identifier = identifier
        super().__init__(f"No prompt found for identifier '{identifier}'")


class PromptValidationError(PromptError):
    """Raised when a stored prompt definition itself is malformed (bad frontmatter, missing
    required metadata fields, invalid version) or the provider fails unexpectedly."""

    def __init__(self, identifier: str, message: str) -> None:
        self.identifier = identifier
        self.message = message
        super().__init__(f"Invalid prompt definition for '{identifier}': {message}")


class PromptRenderError(PromptError):
    """Raised when rendering fails: a missing required variable, or a template placeholder
    outside the known variable set."""

    def __init__(self, identifier: str, message: str) -> None:
        self.identifier = identifier
        self.message = message
        super().__init__(f"Failed to render prompt '{identifier}': {message}")

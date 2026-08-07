"""Unit tests for PromptManager: render, metadata, missing prompt, provider failure
normalization.
"""

from pathlib import Path

import pytest

from src.prompts.exceptions import PromptNotFoundError, PromptValidationError
from src.prompts.filesystem_provider import FileSystemPromptProvider
from src.prompts.manager import PromptManager
from src.prompts.models import PromptDefinition, PromptMetadata, PromptRenderContext, PromptVersion


def _build_manager(tmp_path: Path) -> PromptManager:
    provider = FileSystemPromptProvider(prompts_root=tmp_path)
    return PromptManager(provider=provider)


def _write_prompt(root: Path, namespace_dir: str, name: str, content: str) -> None:
    directory = root / namespace_dir
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.md").write_text(content, encoding="utf-8")


VALID_PROMPT = """---
version: "1.0.0"
purpose: "Manager test prompt."
required_variables:
  - agentName
---
Hello {agentName}, conversation {conversationId}.
"""


async def test_render_returns_a_rendered_prompt_with_metadata(tmp_path: Path) -> None:
    _write_prompt(tmp_path, "supervisor", "system", VALID_PROMPT)
    manager = _build_manager(tmp_path)

    rendered = await manager.render(
        "supervisor.system",
        PromptRenderContext(agent_name="SupervisorAgent", conversation_id="conv-1"),
    )

    assert rendered.identifier == "supervisor.system"
    assert rendered.text == "Hello SupervisorAgent, conversation conv-1."
    assert rendered.metadata.purpose == "Manager test prompt."
    assert str(rendered.metadata.version) == "1.0.0"


async def test_render_propagates_prompt_not_found_error(tmp_path: Path) -> None:
    manager = _build_manager(tmp_path)

    with pytest.raises(PromptNotFoundError):
        await manager.render("does_not_exist.system", PromptRenderContext())


async def test_get_metadata_returns_metadata_without_rendering(tmp_path: Path) -> None:
    _write_prompt(tmp_path, "claims", "system", VALID_PROMPT)
    manager = _build_manager(tmp_path)

    metadata = await manager.get_metadata("claims.system")

    assert metadata.identifier == "claims.system"
    assert metadata.required_variables == ["agentName"]


async def test_get_metadata_propagates_prompt_not_found_error(tmp_path: Path) -> None:
    manager = _build_manager(tmp_path)

    with pytest.raises(PromptNotFoundError):
        await manager.get_metadata("does_not_exist.system")


class _ExplodingProvider:
    """Stub provider that always raises a generic, non-Prompt exception, to test that
    PromptManager normalizes unexpected provider failures into a typed exception."""

    async def load(self, identifier: str) -> PromptDefinition:
        raise RuntimeError("synthetic provider failure")


async def test_unexpected_provider_failure_is_normalized_to_prompt_validation_error() -> None:
    manager = PromptManager(provider=_ExplodingProvider())

    with pytest.raises(PromptValidationError):
        await manager.render("anything.system", PromptRenderContext())


class _StubProvider:
    def __init__(self, definition: PromptDefinition) -> None:
        self._definition = definition

    async def load(self, identifier: str) -> PromptDefinition:
        return self._definition


async def test_render_fails_explicitly_when_a_required_variable_is_missing() -> None:
    definition = PromptDefinition(
        metadata=PromptMetadata(
            identifier="stub.prompt",
            version=PromptVersion(major=1, minor=0, patch=0),
            purpose="stub",
            required_variables=["agentName"],
        ),
        template="agent={agentName}",
    )
    manager = PromptManager(provider=_StubProvider(definition))

    with pytest.raises(Exception, match="Missing required variable"):
        await manager.render("stub.prompt", PromptRenderContext(agent_name=None))

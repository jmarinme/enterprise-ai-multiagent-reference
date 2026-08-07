"""Unit tests for FileSystemPromptProvider: prompt lookup, loading, missing prompt, metadata,
version handling, and malformed prompt definitions.
"""

from pathlib import Path

import pytest

from src.prompts.exceptions import PromptNotFoundError, PromptValidationError
from src.prompts.filesystem_provider import FileSystemPromptProvider
from src.prompts.models import PromptVersion


def _write_prompt(root: Path, namespace_dir: str, name: str, content: str) -> None:
    directory = root / namespace_dir
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.md").write_text(content, encoding="utf-8")


VALID_PROMPT = """---
version: "1.2.3"
purpose: "Test prompt for provider unit tests."
allowed_tools:
  - "some_tool"
prohibited_decisions:
  - "Must not do X."
change_notes: "Initial test version."
required_variables:
  - agentName
---
Hello {agentName}, conversation {conversationId}.
"""


async def test_load_returns_a_prompt_definition_for_a_known_identifier(tmp_path: Path) -> None:
    _write_prompt(tmp_path, "supervisor", "system", VALID_PROMPT)
    provider = FileSystemPromptProvider(prompts_root=tmp_path)

    definition = await provider.load("supervisor.system")

    assert definition.metadata.identifier == "supervisor.system"
    assert "Hello {agentName}" in definition.template


async def test_load_populates_metadata_from_frontmatter(tmp_path: Path) -> None:
    _write_prompt(tmp_path, "claims", "system", VALID_PROMPT)
    provider = FileSystemPromptProvider(prompts_root=tmp_path)

    definition = await provider.load("claims.system")

    assert definition.metadata.version == PromptVersion(major=1, minor=2, patch=3)
    assert definition.metadata.purpose == "Test prompt for provider unit tests."
    assert definition.metadata.allowed_tools == ["some_tool"]
    assert definition.metadata.prohibited_decisions == ["Must not do X."]
    assert definition.metadata.change_notes == "Initial test version."
    assert definition.metadata.required_variables == ["agentName"]


async def test_load_raises_prompt_not_found_for_unknown_namespace(tmp_path: Path) -> None:
    provider = FileSystemPromptProvider(prompts_root=tmp_path)

    with pytest.raises(PromptNotFoundError):
        await provider.load("does_not_exist.system")


async def test_load_raises_prompt_not_found_when_file_is_missing(tmp_path: Path) -> None:
    (tmp_path / "claims").mkdir(parents=True, exist_ok=True)
    provider = FileSystemPromptProvider(prompts_root=tmp_path)

    with pytest.raises(PromptNotFoundError):
        await provider.load("claims.does_not_exist")


async def test_load_raises_prompt_not_found_for_malformed_identifier(tmp_path: Path) -> None:
    provider = FileSystemPromptProvider(prompts_root=tmp_path)

    with pytest.raises(PromptNotFoundError):
        await provider.load("not_a_dotted_identifier")


async def test_load_raises_prompt_validation_error_for_invalid_version(tmp_path: Path) -> None:
    bad_version_prompt = VALID_PROMPT.replace('version: "1.2.3"', 'version: "not-a-version"')
    _write_prompt(tmp_path, "supervisor", "system", bad_version_prompt)
    provider = FileSystemPromptProvider(prompts_root=tmp_path)

    with pytest.raises(PromptValidationError):
        await provider.load("supervisor.system")


@pytest.mark.parametrize(
    "malformed_content",
    [
        "No frontmatter delimiter at all.\nJust body text.",
        "---\nversion: \"1.0.0\"\nNo closing delimiter.",
        "---\nversion: [unclosed\n---\nBody.",
        "---\njust_a_scalar_string\n---\nBody.",
    ],
    ids=["missing_delimiter", "unterminated", "bad_yaml_syntax", "non_mapping_frontmatter"],
)
async def test_load_raises_prompt_validation_error_for_malformed_prompt(
    tmp_path: Path, malformed_content: str
) -> None:
    _write_prompt(tmp_path, "supervisor", "system", malformed_content)
    provider = FileSystemPromptProvider(prompts_root=tmp_path)

    with pytest.raises(PromptValidationError):
        await provider.load("supervisor.system")


async def test_broker_namespace_maps_to_broker_services_directory(tmp_path: Path) -> None:
    """Proves the identifier -> directory mapping is a real abstraction, not a trivial rename."""
    _write_prompt(tmp_path, "broker_services", "system", VALID_PROMPT)
    provider = FileSystemPromptProvider(prompts_root=tmp_path)

    definition = await provider.load("broker.system")

    assert definition.metadata.identifier == "broker.system"


async def test_all_real_shipped_prompts_load_successfully() -> None:
    """Validates the actual prompt content under configs/prompts/, not just test fixtures."""
    provider = FileSystemPromptProvider(prompts_root=Path("configs/prompts"))

    for identifier in (
        "supervisor.system",
        "claims.system",
        "broker.system",
        "commercial.system",
        "fallback.system",
    ):
        definition = await provider.load(identifier)
        assert definition.metadata.purpose
        assert definition.template

"""Local FileSystemPromptProvider: prompt definitions are Markdown files with YAML
frontmatter, stored under configs/prompts/ (CLAUDE.md §6/§9 — "configs/prompts/ contains
versioned prompts"). This is the only place in the codebase that knows about file paths, YAML,
or Markdown — swapping in a future Azure-backed provider requires no change to PromptManager
or any Agent, only a new class implementing the same PromptProvider Protocol.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from src.prompts.exceptions import PromptNotFoundError, PromptValidationError
from src.prompts.models import PromptDefinition, PromptMetadata, PromptVersion

_FRONTMATTER_DELIMITER = "---"

# Logical namespace (the first segment of a dotted identifier, e.g. "claims" in
# "claims.system") to the actual configs/prompts/ subdirectory. Deliberately not always
# identical — this mapping is exactly what lets Agents use short, stable logical identifiers
# ("broker.system") independent of the repository's existing folder names
# ("configs/prompts/broker_services/", already established in CLAUDE.md §6 / PBI-00-01).
_NAMESPACE_TO_DIRECTORY = {
    "supervisor": "supervisor",
    "claims": "claims",
    "broker": "broker_services",
    "commercial": "commercial_intake",
    "fallback": "fallback",
}


class FileSystemPromptProvider:
    """PromptProvider backed by Markdown files with YAML frontmatter under a root directory."""

    def __init__(self, prompts_root: Path) -> None:
        self._prompts_root = prompts_root

    async def load(self, identifier: str) -> PromptDefinition:
        path = self._resolve_path(identifier)
        if path is None or not path.is_file():
            raise PromptNotFoundError(identifier)

        raw = path.read_text(encoding="utf-8")
        frontmatter, template = self._split_frontmatter(identifier, raw)

        try:
            metadata = PromptMetadata(
                identifier=identifier,
                version=PromptVersion.parse(str(frontmatter.get("version", ""))),
                purpose=frontmatter.get("purpose", ""),
                allowed_tools=frontmatter.get("allowed_tools") or [],
                prohibited_decisions=frontmatter.get("prohibited_decisions") or [],
                change_notes=frontmatter.get("change_notes"),
                required_variables=frontmatter.get("required_variables") or [],
            )
        except (ValidationError, ValueError) as exc:
            raise PromptValidationError(identifier, str(exc)) from exc

        return PromptDefinition(metadata=metadata, template=template.strip())

    def _resolve_path(self, identifier: str) -> Path | None:
        parts = identifier.split(".")
        if len(parts) != 2:
            return None
        namespace, name = parts
        directory = _NAMESPACE_TO_DIRECTORY.get(namespace)
        if directory is None:
            return None
        return self._prompts_root / directory / f"{name}.md"

    def _split_frontmatter(self, identifier: str, raw: str) -> tuple[dict[str, Any], str]:
        lines = raw.splitlines()
        if not lines or lines[0].strip() != _FRONTMATTER_DELIMITER:
            raise PromptValidationError(identifier, "Missing YAML frontmatter delimiter")
        try:
            closing_index = lines[1:].index(_FRONTMATTER_DELIMITER) + 1
        except ValueError as exc:
            raise PromptValidationError(identifier, "Unterminated YAML frontmatter") from exc

        frontmatter_text = "\n".join(lines[1:closing_index])
        body = "\n".join(lines[closing_index + 1 :])

        try:
            frontmatter = yaml.safe_load(frontmatter_text) or {}
        except yaml.YAMLError as exc:
            raise PromptValidationError(identifier, f"Malformed YAML frontmatter: {exc}") from exc

        if not isinstance(frontmatter, dict):
            raise PromptValidationError(identifier, "Frontmatter must be a YAML mapping")

        return frontmatter, body

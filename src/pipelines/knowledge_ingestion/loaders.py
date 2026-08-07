"""Document loaders (PBI-03-03): turn one source file into one or more typed IngestionChunks.

DocumentLoader is intentionally a narrow Protocol (matches(path) -> bool, load(path) ->
list[IngestionChunk]) so that adding a new source type — including a future SharePoint
integration pulling documents over Microsoft Graph instead of the local filesystem — never
requires changing KnowledgeIngestionPipeline, only registering one more loader with it. Nothing
here is async: parsing a file already on disk is CPU/disk-bound, not network I/O (matching
src.rag.local_provider.LocalKnowledgeProvider's own synchronous parsing) — a future
network-backed loader (SharePoint) can still implement this same Protocol, doing its own
async fetch-then-parse internally before returning the same typed list[IngestionChunk].
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Protocol

import yaml
from pydantic import ValidationError

from src.pipelines.knowledge_ingestion.exceptions import (
    DocumentParseError,
    UnsupportedDocumentTypeError,
)
from src.pipelines.knowledge_ingestion.models import IngestionChunk

_FRONTMATTER_DELIMITER = "---"
_SECTION_HEADER_PATTERN = re.compile(r"^##\s+(.+)$", re.MULTILINE)
_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    return _SLUG_PATTERN.sub("-", text.strip().lower()).strip("-")


class DocumentLoader(Protocol):
    """Contract every source-type loader implements."""

    def matches(self, path: Path) -> bool:
        """Whether this loader handles path, based on its extension."""
        ...

    def load(self, path: Path) -> list[IngestionChunk]:
        """Parses path into one or more typed IngestionChunks. Raises DocumentParseError (or
        UnsupportedDocumentTypeError) rather than returning a partial/invalid result."""
        ...


class MarkdownDocumentLoader:
    """Loads a Markdown file with a YAML frontmatter block (source_id, title, category,
    optional version), the same shape src.rag.local_provider.LocalKnowledgeProvider already
    reads. Splits the body on top-level ("## ") headers into one IngestionChunk per section
    (section populated with the header text, chunk_id derived from it) when such headers
    exist; otherwise the whole body becomes a single chunk (section=None), matching
    LocalKnowledgeProvider's existing one-chunk-per-document behavior for documents with no
    such internal structure.
    """

    SUPPORTED_SUFFIXES = (".md",)

    def matches(self, path: Path) -> bool:
        return path.suffix.lower() in self.SUPPORTED_SUFFIXES

    def load(self, path: Path) -> list[IngestionChunk]:
        raw = path.read_text(encoding="utf-8")
        frontmatter, body = self._split_frontmatter(path, raw)
        try:
            source_id = frontmatter["source_id"]
            title = frontmatter["title"]
            category = frontmatter["category"]
        except KeyError as exc:
            raise DocumentParseError(
                str(path), f"missing required frontmatter field {exc}"
            ) from exc
        version = str(frontmatter.get("version", "1.0.0"))

        sections = self._split_sections(body)
        if len(sections) == 1 and sections[0][0] is None:
            chunks = [
                self._build_chunk(
                    path, source_id, title, category, version, section=None, text=sections[0][1]
                )
            ]
        else:
            chunks = [
                self._build_chunk(
                    path, source_id, title, category, version, section=heading, text=text
                )
                for heading, text in sections
            ]

        if not chunks or all(not chunk.text.strip() for chunk in chunks):
            raise DocumentParseError(str(path), "document body is empty")
        return chunks

    def _build_chunk(
        self,
        path: Path,
        source_id: str,
        title: str,
        category: str,
        version: str,
        section: str | None,
        text: str,
    ) -> IngestionChunk:
        chunk_id = source_id if section is None else f"{source_id}--{_slugify(section)}"
        try:
            return IngestionChunk(
                chunk_id=chunk_id,
                source_id=source_id,
                title=title,
                category=category,
                section=section,
                source_path=str(path),
                text=text.strip(),
                version=version,
            )
        except ValidationError as exc:
            raise DocumentParseError(str(path), str(exc)) from exc

    @staticmethod
    def _split_sections(body: str) -> list[tuple[str | None, str]]:
        matches = list(_SECTION_HEADER_PATTERN.finditer(body))
        if not matches:
            return [(None, body)]

        sections: list[tuple[str | None, str]] = []
        # Any text before the first "## " header (if non-blank) is captured as its own,
        # unsectioned lead-in chunk — otherwise it would be silently dropped.
        preamble = body[: matches[0].start()].strip()
        if preamble:
            sections.append((None, preamble))

        for index, match in enumerate(matches):
            heading = match.group(1).strip()
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
            sections.append((heading, body[start:end]))
        return sections

    def _split_frontmatter(self, path: Path, raw: str) -> tuple[dict[str, Any], str]:
        lines = raw.splitlines()
        if not lines or lines[0].strip() != _FRONTMATTER_DELIMITER:
            raise DocumentParseError(str(path), "missing YAML frontmatter delimiter")
        try:
            closing_index = lines[1:].index(_FRONTMATTER_DELIMITER) + 1
        except ValueError as exc:
            raise DocumentParseError(str(path), "unterminated YAML frontmatter") from exc

        frontmatter_text = "\n".join(lines[1:closing_index])
        body = "\n".join(lines[closing_index + 1 :]).strip()

        try:
            frontmatter = yaml.safe_load(frontmatter_text) or {}
        except yaml.YAMLError as exc:
            raise DocumentParseError(str(path), f"malformed YAML frontmatter: {exc}") from exc
        if not isinstance(frontmatter, dict):
            raise DocumentParseError(str(path), "frontmatter must be a YAML mapping")

        return frontmatter, body


class PdfDocumentLoader:
    """PDF ingestion abstraction (PBI-03-03): the DocumentLoader interface is fully
    implemented and this loader can be registered with KnowledgeIngestionPipeline today, but
    load() deliberately raises UnsupportedDocumentTypeError rather than performing real text
    extraction. No PDF-parsing library (e.g. pypdf) is a dependency of this project, and
    CLAUDE.md §7 ("do not introduce dependencies... unless explicitly required") means one
    should not be added speculatively — real PDF support is a small, well-scoped future PBI:
    add the parsing dependency, implement load() here, and register this same loader class
    with the pipeline. No other code changes anywhere in this package would be required.
    """

    SUPPORTED_SUFFIXES = (".pdf",)

    def matches(self, path: Path) -> bool:
        return path.suffix.lower() in self.SUPPORTED_SUFFIXES

    def load(self, path: Path) -> list[IngestionChunk]:
        raise UnsupportedDocumentTypeError(
            str(path),
            "PDF ingestion is an abstraction only in PBI-03-03 — no PDF-parsing dependency "
            "is installed. Add one (e.g. pypdf) and implement extraction here to enable it.",
        )

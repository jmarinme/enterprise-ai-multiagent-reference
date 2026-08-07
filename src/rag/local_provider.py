"""LocalKnowledgeProvider: deterministic keyword/text-scoring retrieval over a small set of
synthetic Markdown documents loaded from disk. No embeddings, no vector database, no external
calls — isolated behind the KnowledgeProvider Protocol so a future AzureAISearchProvider can
replace it with zero change to KnowledgeRetriever or any Agent (CLAUDE.md §4.4).

Documents are Markdown files with a YAML frontmatter block (source_id, title, category)
followed by the document body — the same file shape as configs/prompts/, not code-shared with
FileSystemPromptProvider since the two schemas differ and this is the framework's first data
point (see docs/sprint_02/decisions.md).

Each document is treated as exactly one chunk — this synthetic knowledge base is a handful of
short documents, so within-document chunking would add complexity with no present benefit;
revisit once real, longer documents are ingested.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from src.rag.exceptions import KnowledgeProviderError
from src.rag.models import KnowledgeChunk, KnowledgeMetadata, KnowledgeQuery, KnowledgeResult

_FRONTMATTER_DELIMITER = "---"
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_PATTERN.findall(text.lower()))


def _score(query_tokens: set[str], chunk_text: str) -> float:
    """Deterministic keyword-overlap ratio: |query tokens ∩ chunk tokens| / |query tokens|."""
    if not query_tokens:
        return 0.0
    overlap = query_tokens & _tokenize(chunk_text)
    return len(overlap) / len(query_tokens)


class LocalKnowledgeProvider:
    """KnowledgeProvider backed by synthetic Markdown files under a local directory."""

    def __init__(self, documents_root: Path) -> None:
        if not documents_root.is_dir():
            raise KnowledgeProviderError(
                "local", f"documents_root '{documents_root}' is not a directory"
            )
        self._chunks = [
            self._parse_document(path) for path in sorted(documents_root.glob("*.md"))
        ]

    async def retrieve(self, query: KnowledgeQuery) -> KnowledgeResult:
        candidates = self._chunks
        if query.category is not None:
            candidates = [c for c in candidates if c.metadata.category == query.category]

        query_tokens = _tokenize(query.text)
        scored = [
            (score, chunk)
            for chunk in candidates
            if (score := _score(query_tokens, chunk.text)) > 0
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)

        top_chunks = [
            chunk.model_copy(update={"score": score})
            for score, chunk in scored[: query.top_k]
        ]
        return KnowledgeResult(query=query, chunks=top_chunks)

    def _parse_document(self, path: Path) -> KnowledgeChunk:
        raw = path.read_text(encoding="utf-8")
        frontmatter, body = self._split_frontmatter(path, raw)
        try:
            metadata = KnowledgeMetadata(
                source_id=frontmatter["source_id"],
                title=frontmatter["title"],
                category=frontmatter["category"],
            )
        except (ValidationError, KeyError) as exc:
            raise KnowledgeProviderError(
                "local", f"Invalid or missing frontmatter fields in {path.name}: {exc}"
            ) from exc
        return KnowledgeChunk(chunk_id=metadata.source_id, text=body, metadata=metadata)

    def _split_frontmatter(self, path: Path, raw: str) -> tuple[dict[str, Any], str]:
        lines = raw.splitlines()
        if not lines or lines[0].strip() != _FRONTMATTER_DELIMITER:
            raise KnowledgeProviderError(
                "local", f"Missing YAML frontmatter delimiter in {path.name}"
            )
        try:
            closing_index = lines[1:].index(_FRONTMATTER_DELIMITER) + 1
        except ValueError as exc:
            raise KnowledgeProviderError(
                "local", f"Unterminated YAML frontmatter in {path.name}"
            ) from exc

        frontmatter_text = "\n".join(lines[1:closing_index])
        body = "\n".join(lines[closing_index + 1 :]).strip()

        try:
            frontmatter = yaml.safe_load(frontmatter_text) or {}
        except yaml.YAMLError as exc:
            raise KnowledgeProviderError(
                "local", f"Malformed YAML frontmatter in {path.name}: {exc}"
            ) from exc
        if not isinstance(frontmatter, dict):
            raise KnowledgeProviderError(
                "local", f"Frontmatter must be a YAML mapping in {path.name}"
            )

        return frontmatter, body

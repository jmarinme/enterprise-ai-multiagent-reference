"""Unit tests for document loaders (PBI-03-03): Markdown (real parsing, section chunking,
versioning) and the PDF ingestion abstraction (interface present, load() typed-error stub).
"""

from pathlib import Path

import pytest

from src.pipelines.knowledge_ingestion.exceptions import (
    DocumentParseError,
    UnsupportedDocumentTypeError,
)
from src.pipelines.knowledge_ingestion.loaders import MarkdownDocumentLoader, PdfDocumentLoader

_SIMPLE_DOC = """---
source_id: "KB-TEST-0001"
title: "Test Document"
category: "test"
---
A single unsectioned body.
"""

_VERSIONED_DOC = """---
source_id: "KB-TEST-0002"
title: "Versioned Document"
category: "test"
version: "3.1.0"
---
Body text.
"""

_SECTIONED_DOC = """---
source_id: "KB-TEST-0003"
title: "Sectioned Document"
category: "test"
---
Lead-in text before any section.

## First Section

First section body.

## Second Section, With Punctuation!

Second section body.
"""


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_markdown_loader_matches_only_md_files(tmp_path: Path) -> None:
    loader = MarkdownDocumentLoader()

    assert loader.matches(tmp_path / "doc.md") is True
    assert loader.matches(tmp_path / "doc.MD") is True
    assert loader.matches(tmp_path / "doc.pdf") is False


def test_markdown_loader_parses_a_single_unsectioned_document(tmp_path: Path) -> None:
    path = _write(tmp_path, "simple.md", _SIMPLE_DOC)
    loader = MarkdownDocumentLoader()

    chunks = loader.load(path)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.chunk_id == "KB-TEST-0001"
    assert chunk.source_id == "KB-TEST-0001"
    assert chunk.title == "Test Document"
    assert chunk.category == "test"
    assert chunk.section is None
    assert chunk.text == "A single unsectioned body."
    assert chunk.source_path == str(path)
    assert chunk.version == "1.0.0"


def test_markdown_loader_reads_an_explicit_version_from_frontmatter(tmp_path: Path) -> None:
    path = _write(tmp_path, "versioned.md", _VERSIONED_DOC)
    loader = MarkdownDocumentLoader()

    chunks = loader.load(path)

    assert chunks[0].version == "3.1.0"


def test_markdown_loader_splits_h2_sections_into_separate_chunks(tmp_path: Path) -> None:
    path = _write(tmp_path, "sectioned.md", _SECTIONED_DOC)
    loader = MarkdownDocumentLoader()

    chunks = loader.load(path)

    assert len(chunks) == 3
    assert chunks[0].section is None
    assert chunks[0].chunk_id == "KB-TEST-0003"
    assert chunks[0].text == "Lead-in text before any section."

    assert chunks[1].section == "First Section"
    assert chunks[1].chunk_id == "KB-TEST-0003--first-section"
    assert chunks[1].text == "First section body."

    assert chunks[2].section == "Second Section, With Punctuation!"
    assert chunks[2].chunk_id == "KB-TEST-0003--second-section-with-punctuation"
    assert chunks[2].text == "Second section body."


def test_markdown_loader_chunk_ids_are_stable_across_repeated_loads(tmp_path: Path) -> None:
    path = _write(tmp_path, "sectioned.md", _SECTIONED_DOC)
    loader = MarkdownDocumentLoader()

    first_ids = [chunk.chunk_id for chunk in loader.load(path)]
    second_ids = [chunk.chunk_id for chunk in loader.load(path)]

    assert first_ids == second_ids


def test_markdown_loader_raises_for_missing_frontmatter_delimiter(tmp_path: Path) -> None:
    path = _write(tmp_path, "bad.md", "no frontmatter here at all")
    loader = MarkdownDocumentLoader()

    with pytest.raises(DocumentParseError):
        loader.load(path)


def test_markdown_loader_raises_for_unterminated_frontmatter(tmp_path: Path) -> None:
    path = _write(tmp_path, "bad.md", "---\nsource_id: X\nbody with no closing delimiter")
    loader = MarkdownDocumentLoader()

    with pytest.raises(DocumentParseError):
        loader.load(path)


def test_markdown_loader_raises_for_missing_required_frontmatter_field(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "bad.md",
        '---\nsource_id: "KB-X"\ntitle: "Missing category"\n---\nbody\n',
    )
    loader = MarkdownDocumentLoader()

    with pytest.raises(DocumentParseError):
        loader.load(path)


def test_markdown_loader_raises_for_an_empty_body(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "empty.md",
        '---\nsource_id: "KB-X"\ntitle: "Empty"\ncategory: "test"\n---\n\n',
    )
    loader = MarkdownDocumentLoader()

    with pytest.raises(DocumentParseError):
        loader.load(path)


def test_pdf_loader_matches_only_pdf_files(tmp_path: Path) -> None:
    loader = PdfDocumentLoader()

    assert loader.matches(tmp_path / "doc.pdf") is True
    assert loader.matches(tmp_path / "doc.md") is False


def test_pdf_loader_raises_unsupported_document_type_error(tmp_path: Path) -> None:
    """PDF ingestion abstraction (PBI-03-03): the loader is fully wired into the DocumentLoader
    Protocol but deliberately does not perform real extraction — see loaders.py's own
    docstring for why (no PDF-parsing dependency is installed in this project)."""
    path = tmp_path / "doc.pdf"
    path.write_bytes(b"%PDF-1.4 not a real pdf")
    loader = PdfDocumentLoader()

    with pytest.raises(UnsupportedDocumentTypeError):
        loader.load(path)

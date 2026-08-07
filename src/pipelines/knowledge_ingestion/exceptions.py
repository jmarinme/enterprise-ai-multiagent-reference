"""Typed exceptions for the knowledge ingestion pipeline (PBI-03-03).

A distinct hierarchy from src.rag.exceptions (the retrieval-side framework): ingestion is an
offline/batch concern with its own failure modes (a malformed source document, an unsupported
loader, an index schema mismatch) that have nothing to do with a live KnowledgeProvider.retrieve()
call. Mirrors the same "one base exception, specific subclasses for specific failure modes"
shape already used by src.tools.exceptions, src.prompts.exceptions, src.llm.exceptions, and
src.rag.exceptions.
"""

from __future__ import annotations


class IngestionError(Exception):
    """Base class for all knowledge ingestion pipeline errors."""


class IngestionConfigurationError(IngestionError):
    """Raised when required ingestion configuration (index name, endpoint) is missing."""


class DocumentParseError(IngestionError):
    """Raised when a source document cannot be parsed into one or more IngestionChunks."""

    def __init__(self, source_path: str, message: str) -> None:
        self.source_path = source_path
        self.message = message
        super().__init__(f"Failed to parse '{source_path}': {message}")


class UnsupportedDocumentTypeError(IngestionError):
    """Raised when a DocumentLoader is asked to load a document type it does not (yet)
    support — e.g. PdfDocumentLoader today (PBI-03-03 ships the abstraction only; see
    src.pipelines.knowledge_ingestion.loaders.PdfDocumentLoader)."""

    def __init__(self, source_path: str, reason: str) -> None:
        self.source_path = source_path
        self.reason = reason
        super().__init__(f"Cannot ingest '{source_path}': {reason}")


class IndexOperationError(IngestionError):
    """Raised when creating/updating the index schema, or uploading/deleting documents,
    fails against the Azure AI Search management/data plane."""

    def __init__(self, operation: str, message: str) -> None:
        self.operation = operation
        self.message = message
        super().__init__(f"Index operation '{operation}' failed: {message}")

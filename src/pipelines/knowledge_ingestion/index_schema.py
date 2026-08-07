"""Azure AI Search index schema/definition (PBI-03-03) — the single source of truth for field
names, shared by this ingestion pipeline (what gets written) and
src.rag.azure_ai_search_provider.AzureAISearchProvider (what gets read back, via its
_SELECT_FIELDS). Keeping both in Python, rather than duplicating the schema in Bicep, avoids
two competing definitions of the same index drifting apart over time — Bicep continues to
provision only the Azure AI Search *service* (ops/bicep/modules/ai-search.bicep); this module
owns the *index* living inside it, created/updated via the Search REST management API
(SearchIndexClient), the standard, idiomatic way to manage Azure AI Search index schemas.

Every field name here matches src.rag.models.KnowledgeMetadata's own field names plus the two
ingestion-only fields (version, content_hash) needed for incremental ingestion — never a
literal string duplicated elsewhere; src.pipelines.knowledge_ingestion.models.IngestionChunk
and src.rag.azure_ai_search_provider._SELECT_FIELDS both reference the same field names by
construction, not by convention.

The index name itself is never hardcoded here or anywhere in this package — it is always
supplied by the caller, sourced from src.config.settings.KnowledgeSettings.
azure_ai_search_index_name, the exact same setting AzureAISearchProvider itself reads.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure.search.documents.indexes.models import (
    SearchableField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
)

if TYPE_CHECKING:
    from src.pipelines.knowledge_ingestion.models import IngestionChunk

# chunk_id is the key field: stable across re-ingestion runs (see loaders.py for how it is
# derived), which is what makes merge-or-upload-based incremental ingestion and delete-by-id
# both possible.
CHUNK_ID_FIELD = "chunk_id"
CONTENT_FIELD = "content"
SOURCE_ID_FIELD = "source_id"
TITLE_FIELD = "title"
CATEGORY_FIELD = "category"
SECTION_FIELD = "section"
SOURCE_PATH_FIELD = "source_path"
VERSION_FIELD = "version"
CONTENT_HASH_FIELD = "content_hash"


def build_index_definition(index_name: str) -> SearchIndex:
    """Builds the SearchIndex definition for index_name. Callers pass the configured index
    name (never a literal) — see this module's own docstring."""
    fields = [
        SimpleField(name=CHUNK_ID_FIELD, type=SearchFieldDataType.String, key=True),
        SearchableField(name=CONTENT_FIELD),
        SimpleField(name=SOURCE_ID_FIELD, type=SearchFieldDataType.String, filterable=True),
        SearchableField(name=TITLE_FIELD),
        SimpleField(name=CATEGORY_FIELD, type=SearchFieldDataType.String, filterable=True),
        SimpleField(name=SECTION_FIELD, type=SearchFieldDataType.String, filterable=True),
        SimpleField(name=SOURCE_PATH_FIELD, type=SearchFieldDataType.String),
        SimpleField(name=VERSION_FIELD, type=SearchFieldDataType.String),
        SimpleField(name=CONTENT_HASH_FIELD, type=SearchFieldDataType.String, filterable=True),
    ]
    return SearchIndex(name=index_name, fields=fields)


def chunk_to_search_document(chunk: IngestionChunk) -> dict[str, Any]:
    """Maps a typed IngestionChunk onto the index document shape build_index_definition()
    describes — the metadata-mapping half of this PBI's own explicit requirement, co-located
    with the field-name constants it uses so the two can never drift apart."""
    return {
        CHUNK_ID_FIELD: chunk.chunk_id,
        CONTENT_FIELD: chunk.text,
        SOURCE_ID_FIELD: chunk.source_id,
        TITLE_FIELD: chunk.title,
        CATEGORY_FIELD: chunk.category,
        SECTION_FIELD: chunk.section,
        SOURCE_PATH_FIELD: chunk.source_path,
        VERSION_FIELD: chunk.version,
        CONTENT_HASH_FIELD: chunk.content_hash,
    }

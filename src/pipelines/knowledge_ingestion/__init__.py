"""Knowledge ingestion pipeline (PBI-03-03): builds and maintains the Azure AI Search index
src.rag.azure_ai_search_provider.AzureAISearchProvider queries at request time.

DocumentLoader(s) -> IngestionChunk(s) -> EmbeddingProvider (optional) -> KnowledgeIngestionPipeline
-> Azure AI Search index (create-or-update schema, then incremental upload/skip/delete).

Configuration-driven throughout: the index name always comes from
src.config.settings.KnowledgeSettings.azure_ai_search_index_name (the same setting
AzureAISearchProvider itself reads) — never a literal string anywhere in this package.

Grounding compatibility (PBI-02-03): every field src.rag.grounding_models.Citation needs
(document id, section, score, title, source path) is present on IngestionChunk and mapped
1:1 onto the index schema's field names, which are themselves the exact field names
AzureAISearchProvider._SELECT_FIELDS reads back at retrieval time — single source of truth on
both ends of the pipe.

No Agent, Supervisor, Prompt, or Tool code is imported or touched by this package.
"""

from __future__ import annotations

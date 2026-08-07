"""Batch/offline data pipelines (CLAUDE.md §6) — distinct from the request-time frameworks in
src/agents, src/rag, src/core. knowledge_ingestion (PBI-03-03) is the first occupant: it builds
and maintains the Azure AI Search index src.rag.azure_ai_search_provider.AzureAISearchProvider
reads from at request time. Nothing here runs on the request path.
"""

from __future__ import annotations

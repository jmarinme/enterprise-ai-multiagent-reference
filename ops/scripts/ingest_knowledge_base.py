"""Knowledge ingestion CLI (PBI-03-03).

Builds/updates the Azure AI Search index defined by src.pipelines.knowledge_ingestion.
index_schema and ingests every supported document under a source directory (default:
configs/knowledge_base — the same synthetic corpus LocalKnowledgeProvider already reads).

Configuration-driven throughout: endpoint, index name, and auth mode all come from
src.config.settings.KnowledgeSettings — the exact same settings
src.rag.azure_ai_search_provider.AzureAISearchProvider reads at request time. Nothing here is
hardcoded.

This is the composition root for the offline ingestion job, mirroring
apps/api/src/api/dependencies.py's pattern for the request-time API: it is the one place that
constructs concrete SearchIndexClient/SearchClient instances and chooses Managed Identity vs.
API-key auth (via the existing SecretProvider abstraction) — KnowledgeIngestionPipeline itself
never does either.

Usage (not executed as part of any PBI — this file exists but is never run against real Azure
in this repository's own development/validation):

    python ops/scripts/ingest_knowledge_base.py [--documents-root PATH]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from azure.core.credentials import AzureKeyCredential
from azure.core.credentials_async import AsyncTokenCredential
from azure.search.documents.aio import SearchClient
from azure.search.documents.indexes.aio import SearchIndexClient

from src.config.settings import KnowledgeSettings, SecretProviderSettings
from src.domain.secret_provider import SecretProvider
from src.pipelines.knowledge_ingestion.exceptions import IngestionError
from src.pipelines.knowledge_ingestion.loaders import (
    DocumentLoader,
    MarkdownDocumentLoader,
    PdfDocumentLoader,
)
from src.pipelines.knowledge_ingestion.pipeline import KnowledgeIngestionPipeline
from src.services.secret_store.factory import get_secret_provider

_DEFAULT_DOCUMENTS_ROOT = Path("configs/knowledge_base")
_LOADERS: list[DocumentLoader] = [MarkdownDocumentLoader(), PdfDocumentLoader()]


async def _build_credential(
    settings: KnowledgeSettings,
) -> AzureKeyCredential | AsyncTokenCredential:
    if settings.azure_ai_search_use_api_key:
        secret_provider: SecretProvider = get_secret_provider(SecretProviderSettings())
        api_key = await secret_provider.get_secret(settings.azure_ai_search_api_key_secret_name)
        return AzureKeyCredential(api_key)

    from azure.identity.aio import DefaultAzureCredential

    return DefaultAzureCredential()


async def run(documents_root: Path) -> int:
    settings = KnowledgeSettings()
    if not settings.azure_ai_search_endpoint:
        print("AZURE_AI_SEARCH_ENDPOINT must be set to run knowledge ingestion.", file=sys.stderr)
        return 1
    if not settings.azure_ai_search_index_name:
        print("AZURE_AI_SEARCH_INDEX_NAME must be set to run knowledge ingestion.", file=sys.stderr)
        return 1

    credential = await _build_credential(settings)
    index_client = SearchIndexClient(endpoint=settings.azure_ai_search_endpoint, credential=credential)
    search_client = SearchClient(
        endpoint=settings.azure_ai_search_endpoint,
        index_name=settings.azure_ai_search_index_name,
        credential=credential,
    )
    pipeline = KnowledgeIngestionPipeline(
        index_client=index_client,
        search_client=search_client,
        index_name=settings.azure_ai_search_index_name,
        loaders=_LOADERS,
    )

    try:
        await pipeline.ensure_index()
        report = await pipeline.ingest(documents_root)
    except IngestionError as exc:
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await search_client.close()
        await index_client.close()
        if hasattr(credential, "close"):
            await credential.close()

    print(f"Index: {report.index_name}")
    print(f"Uploaded (new/changed): {len(report.uploaded_chunk_ids)} — {report.uploaded_chunk_ids}")
    print(f"Unchanged (skipped): {len(report.unchanged_chunk_ids)}")
    print(f"Deleted (stale): {len(report.deleted_chunk_ids)} — {report.deleted_chunk_ids}")
    if report.has_failures:
        print(f"Failed: {len(report.failed)}", file=sys.stderr)
        for path, message in report.failed.items():
            print(f"  {path}: {message}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--documents-root",
        type=Path,
        default=_DEFAULT_DOCUMENTS_ROOT,
        help="Directory of source documents to ingest (default: configs/knowledge_base).",
    )
    args = parser.parse_args()
    return asyncio.run(run(args.documents_root))


if __name__ == "__main__":
    raise SystemExit(main())

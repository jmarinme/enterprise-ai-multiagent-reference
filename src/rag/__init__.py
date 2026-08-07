"""Knowledge/RAG retrieval framework (PBI-02-01).

Agent -> KnowledgeRetriever -> KnowledgeProvider -> KnowledgeResult -> PromptManager ->
LLMProvider. Agents depend only on KnowledgeRetriever and the typed models in this package —
never on a concrete provider or a search technology (CLAUDE.md §4.4). RAG is documentary only:
retrieved chunks are reference/contextual information, never a substitute for a Tool-sourced
business fact.
"""

from __future__ import annotations

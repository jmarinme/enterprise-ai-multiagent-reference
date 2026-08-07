"""LLMProvider Protocol — the only interface Agents depend on.

Neither Agents nor any other framework file may import an Azure SDK or the OpenAI SDK
directly. Only concrete provider implementations (mock_provider.py, azure_openai_provider.py)
do, and only azure_openai_provider.py imports Azure/OpenAI packages at all.
"""

from __future__ import annotations

from typing import Protocol

from src.llm.models import LLMRequest, LLMResponse


class LLMProvider(Protocol):
    """Contract for generating a completion from a request."""

    async def generate(self, request: LLMRequest) -> LLMResponse: ...

# Sprint 03 Implementation Plan

## PBI-03-01 — Ollama LLM Provider and local runtime

Adds `OllamaLLMProvider` (`src/llm/ollama_provider.py`) as a third `LLMProvider` implementation,
structurally mirroring `AzureOpenAIProvider`'s proven shape (PBI-01-04): lazy `aiohttp` import
(never required unless `LLM_PROVIDER=ollama`), typed exception mapping (timeout/connection/HTTP
failures normalized into the existing `LLMTimeoutError`/`LLMRateLimitError`/`LLMProviderError`/
`LLMConfigurationError` hierarchy — no new exception types needed), and construction-time
validation of required configuration. Provider selection becomes configuration-driven via a new
branch in `src/llm/factory.py`; `apps/api/src/api/dependencies.py` needs zero changes since it
already delegates entirely to the factory. `MockLLMProvider` remains the default for every test
and local dev run unless explicitly overridden.

Tool Calling (PBI-02-04) support is mapped best-effort to Ollama's documented OpenAI-compatible
`tools=`/`message.tool_calls` API shape, with two documented, Ollama-specific differences from
the OpenAI provider: tool calls carry no `id` (one is synthesized) and `arguments` arrive as an
already-parsed dict, not a JSON-encoded string. This mapping is implemented per Ollama's public
API documentation but not live-verified against a real Ollama server with a tool-calling-capable
model, since neither was available in this development environment — see `decisions.md`. This is
safe by construction: a model that doesn't support tool calling simply returns no `tool_calls`,
which `ToolCallingOrchestrator` already treats as "the LLM chose not to call anything," so the
deterministic Claims workflow can never be put at risk by this gap.

`docker-compose.yml` gains `extra_hosts: host.docker.internal:host-gateway` on the `api` service
so a containerized API can reach a host-run Ollama server — Ollama itself is never containerized
(host-run, opt-in, per the PBI's own instruction). `apps/api/Dockerfile`'s pip-install list gains
`aiohttp` so the Ollama path is genuinely functional inside the built image. `.env.example`
documents every environment variable a fully local (`mock` or `ollama`, `in_memory` conversation
store, `local` knowledge provider — zero Azure dependency) run requires.

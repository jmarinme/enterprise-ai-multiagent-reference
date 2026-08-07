# Sprint 03 Decisions and Deviations

Record sprint-specific decisions and deviations. Cross-sprint decisions belong in ADRs.

## 2026-08-07 — PBI-03-01: `OllamaLLMProvider` uses `aiohttp`, not a new `ollama` SDK dependency

**Decision:** `OllamaLLMProvider` hand-rolls a POST to Ollama's documented `/api/chat` REST endpoint using `aiohttp`, lazily imported, rather than adding the official `ollama` PyPI package as a new dependency. `aiohttp` is already a declared, installed transitive dependency of every existing Azure extra (`cosmos`, `keyvault`, `azureopenai`, `azuresearch`) in this project — reusing it avoids introducing a new third-party SDK for what is a single, well-documented, stable REST call, consistent with CLAUDE.md §7 ("do not introduce dependencies... unless explicitly required").

**Deviation/status change:** None — a direct application of the existing dependency-reuse precedent.

**How to apply:** Any future provider needing simple async HTTP should default to `aiohttp` (already proven in this dependency tree) before adding a new HTTP client library or vendor SDK.

## 2026-08-07 — PBI-03-01: Ollama's own configured timeout takes precedence over `LLMGenerationSettings.timeout_seconds`

**Decision:** `OllamaLLMProvider.generate()` uses `self._timeout_seconds` (from `OLLAMA_TIMEOUT_SECONDS`, default 60s) for the `aiohttp.ClientTimeout`, rather than `request.settings.timeout_seconds` (which `AzureOpenAIProvider` uses directly, defaulting to 30s). Local CPU/GPU inference latency is structurally different from a cloud API call and, in live testing during this PBI, a single real turn against a 3B local model with tool-calling took ~49 seconds — well past `LLMGenerationSettings`' 30s default. A dedicated, provider-level, infra-tuned timeout is the correct place for this, not a change to `LLMGenerationSettings`' own cloud-API-tuned default (which would affect Azure OpenAI too).

**Deviation/status change:** A deliberate, documented divergence from `AzureOpenAIProvider`'s own timeout-handling pattern, justified by measured local-inference latency, not an oversight.

**How to apply:** If a future PBI needs Ollama generation calls to also honor a per-call `LLMGenerationSettings.timeout_seconds` override (e.g. a caller wanting a strict 10s budget), `max(request.settings.timeout_seconds, self._timeout_seconds)` would be the point to revisit this — not before, since no caller currently needs it.

## 2026-08-07 — PBI-03-01: Ollama Tool Calling mapping implemented per documented API shape, not live-verified until this PBI's own smoke test

**Decision:** `_to_ollama_tools`/`_from_ollama_tool_calls` map `LLMToolDefinition`/`ToolCallRequest` to/from Ollama's documented OpenAI-compatible `tools=`/`message.tool_calls` shape, with two Ollama-specific adaptations: a synthesized `call_id` (Ollama's `tool_calls` carry none) and direct dict arguments (no JSON-string decoding, unlike OpenAI). This was written against Ollama's public API documentation. During this PBI's own validation, a real local Ollama server (`llama3.2:3b`, which self-reports `"capabilities":["completion","tools"]`) turned out to be running in this development environment, so the mapping WAS live-verified end to end through a real `POST /chat` call — the model genuinely requested `claim_registration` and it executed successfully via the real `ToolCallingOrchestrator`/`ToolExecutor` path (see `validation.md`).

**Deviation/status change:** An upgrade from the PBI's own anticipated fallback ("if not supported... document the limitation") — a real, positive verification was possible and performed. The mapping is now confirmed correct against at least one real Ollama model/version, though it remains unverified against every other Ollama version or model family, which may format `tool_calls` differently or not support tool-calling at all.

**How to apply:** Do not assume every Ollama model/version behaves identically — the safe design already accounts for this: a model that doesn't support tool calling (or an older Ollama version) simply returns no `tool_calls`, which `ToolCallingOrchestrator` treats as "the LLM chose not to call anything," never breaking the deterministic Claims workflow.

## 2026-08-07 — PBI-03-01: live Ollama smoke test surfaced a real architectural observation about LLM-fabricated Tool arguments

**Decision/Observation:** In the live smoke test, `llama3.2:3b` requested `claim_registration` (one of `CLAIMS_ALLOWED_TOOLS`) and supplied plausible-looking values for every required field (`policy_number`, `event_date`, `event_location`, `loss_type`, `loss_description`, `contact_name`, `contact_phone`) **without the user having provided any of them yet** — the deterministic `advance_claims_intake` state machine had only reached "ask for policy_number" at that point, and its own business-fact response text ("Could you provide your policy number?") is what the API actually returned to the user, completely uncorrupted. The Tool Calling framework's own additive isolation (PBI-02-04: `AgentResponse.tool_calls` is a separate field, never feeding into `ClaimsIntakeState` or the response text) is exactly what prevented this LLM-fabricated registration from being mistaken for, or contaminating, the real business flow — the synthetic claim it registered (`SYN-CLM-2026-0001`) is inert data with no bearing on the actual conversation's outcome.

**Deviation/status change:** Not a defect — this is the isolation boundary (CLAUDE.md §3, "the LLM is not the source of truth") working exactly as designed, observed under real conditions for the first time in this project. Flagged here because it is a genuinely important, non-obvious operational insight this live test surfaced, not something a mocked test could have shown as convincingly.

**How to apply:** Any future PBI that considers connecting Tool Calling's demonstration path to a Tool with real, irreversible side effects (as opposed to this project's synthetic registrar Tools) must add an explicit confirmation/authorization step before execution — an LLM will confidently fabricate plausible-looking arguments for a required field it was never actually told, and nothing in the current design stops that from reaching `ToolExecutor` for an allow-listed Tool. This is worth an ADR before any such wiring is attempted, even against synthetic data.

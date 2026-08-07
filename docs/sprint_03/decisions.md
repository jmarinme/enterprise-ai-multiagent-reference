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

## 2026-08-07 — PBI-03-02: `knowledgeProvider` defaults to `local`, not `azure_ai_search`, in every Bicep parameter file

**Decision:** `main.bicep`'s `knowledgeProvider` param, and every one of `dev`/`staging`/`prod.bicepparam`, set `knowledgeProvider = 'local'` even though this PBI's whole purpose is wiring the Azure runtime. `llmProvider` and `conversationStoreProvider` both default to their Azure-backed values (`azure_openai`, `cosmos`) because this same template fully provisions everything either one needs to actually work (the Azure OpenAI deployment; the Cosmos database/container/RBAC). Azure AI Search is different: `AzureAISearchProvider.__init__` raises `KnowledgeConfigurationError` if `AZURE_AI_SEARCH_INDEX_NAME` is empty, and no index exists — index creation/ingestion is explicitly out of scope for PBI-03-02. Defaulting `knowledgeProvider` to `azure_ai_search` would therefore have shipped a Container App configuration that fails at startup on every request needing knowledge retrieval, the first time this template was actually deployed.

**Deviation/status change:** A deliberate, safety-driven divergence from "wire everything to Azure by default," not an oversight or an incomplete implementation — the env var plumbing for Azure AI Search (`AZURE_AI_SEARCH_ENDPOINT`, `AZURE_AI_SEARCH_INDEX_NAME`) is fully wired and correct; only the *default selection* stays `local` until the index genuinely exists.

**How to apply:** The future PBI that creates the AI Search index and ingests documents should, as its last step, flip `knowledgeProvider` to `'azure_ai_search'` in the parameter files that should use it — the `aiSearchIndexName` param already exists and defaults to a real placeholder name (`tmxai-knowledge-index`) so that PBI only needs to point the ingestion pipeline at the same name, not invent new plumbing.

## 2026-08-07 — PBI-03-02: Azure OpenAI local (key) auth left enabled, mirroring Azure AI Search's own precedent

**Decision:** `azure-openai.bicep`'s Cognitive Services account does not set `disableLocalAuth: true` (unlike `cosmos-db.bicep`, which does). This repeats PBI-02-02's own reasoning for Azure AI Search verbatim: `AzureOpenAIProvider` explicitly supports an opt-in `azure_openai_use_api_key` path via `SecretProvider`, so the resource-level door must stay open for that path to remain real and exercisable; Managed Identity (Entra ID) remains the default in both the Bicep RBAC assignment and the Python provider. No key is created, stored, or output by this module.

**Deviation/status change:** None — a direct, symmetric application of the precedent PBI-02-02 already established and documented, extended to the one remaining Azure provider that has the same opt-in-key-auth requirement.

**How to apply:** If a future ADR decides key-based auth should never be used against Azure OpenAI in any environment (the same trigger condition PBI-02-02's own decisions.md already names for AI Search), that is the point to set `disableLocalAuth: true` here too.

## 2026-08-07 — PBI-03-02: composition-root tests use an autouse `lru_cache`-clearing fixture, not per-test dependency overrides

**Decision:** `tests/unit/api/test_dependencies.py` calls `.cache_clear()` on every `@lru_cache`-decorated function in `apps/api/src/api/dependencies.py` via an autouse fixture (before AND after each test), rather than using FastAPI's `app.dependency_overrides` mechanism or constructing a fresh, uncached module instance per test. `dependencies.py`'s functions are plain module-level `@lru_cache` singletons, not real FastAPI `Depends()`-injected callables with override support in the way route handlers are — the cache-clearing approach directly matches how the composition root is actually implemented, and guarantees no test in this file (or, critically, any *other* test file in the suite, such as `test_chat.py`, which builds `main.app` via `TestClient` and transitively calls `get_supervisor()`) can ever observe a provider built from a previous test's monkeypatched environment variables.

**Deviation/status change:** None — a new test file for previously untested code, not a change to any existing test's approach.

**How to apply:** Any future test file that exercises `apps/api/src/api/dependencies.py` directly (as opposed to going through the HTTP layer via `TestClient`, which already gets a consistent, real request-response cycle) must use this same clear-before-and-after fixture pattern — never rely on test ordering or manual cleanup at the end of only some tests.

## 2026-08-07 — PBI-03-03: the Azure AI Search index schema is defined in Python, not duplicated in Bicep

**Decision:** `src/pipelines/knowledge_ingestion/index_schema.py::build_index_definition()` is the single, authoritative definition of the Azure AI Search index's fields, written using `azure.search.documents.indexes.models` (the same SDK package `AzureAISearchProvider` already depends on) and applied via `SearchIndexClient.create_or_update_index()`. No `Microsoft.Search/searchServices/indexes` Bicep resource was added, even though that ARM resource type exists and could theoretically declare a schema too. Bicep (`ops/bicep/modules/ai-search.bicep`) continues to provision only the search *service*, unchanged this PBI.

**Deviation/status change:** None — a deliberate architecture choice, not an oversight or an incomplete implementation. The ingestion pipeline needs the schema programmatically anyway (to create/update the index before writing to it), and `AzureAISearchProvider._SELECT_FIELDS` needs to read the exact same field names back — keeping both in Python, importable from the same module, means a field-name typo or a forgotten field is a Python-level bug (caught by mypy/tests) rather than a silent drift between two independently-maintained schema definitions in two different languages/toolchains. This also matches standard industry practice: Azure AI Search index schemas are conventionally managed via the SDK/REST management API (often as part of an ingestion job, exactly as done here), not IaC templates, since they evolve on a different cadence than infrastructure provisioning.

**How to apply:** Any future field added to the index (e.g. a real vector field, once embeddings are actually implemented) should be added to `build_index_definition()` and, if retrieval needs it, to `AzureAISearchProvider._SELECT_FIELDS` — never to a Bicep template. If a future ADR decides index-as-Bicep is actually required (e.g. for a GitOps-style "everything in IaC" policy), that decision should explicitly address how it will stay in sync with `AzureAISearchProvider`'s own field expectations, since the whole point of this decision is avoiding that drift.

## 2026-08-07 — PBI-03-03: PDF ingestion, real embeddings, and SharePoint integration are abstractions only

**Decision:** `PdfDocumentLoader.load()` raises a typed `UnsupportedDocumentTypeError` rather than extracting real text; `EmbeddingProvider`'s only implementation, `NullEmbeddingProvider`, always returns `None`, and no vector field exists on the index schema; no `SharePointDocumentLoader` was written at all — only a `DocumentLoader` Protocol generic enough for one to implement it later without any pipeline changes. None of these gaps are accidental: no PDF-parsing library (`pypdf`, `pdfplumber`, or similar) is installed anywhere in this project, CLAUDE.md §7 says not to add a dependency unless explicitly required, and every prior RAG PBI (PBI-02-01, PBI-02-02) already excluded vector search as unjustified for this small, synthetic corpus — an exclusion this PBI has no new justification to overturn. A SharePoint SDK dependency and real Graph API integration were never requested.

**Deviation/status change:** None — the PBI's own wording ("pdf ingestion **abstraction**", "embedding pipeline **abstraction**", "**support** ... future SharePoint integration") explicitly asked for abstractions, not full implementations, for exactly these three capabilities.

**How to apply:** Real PDF support: add a parsing dependency (e.g. `pypdf`) as its own new `pyproject.toml` extra (mirroring the `ollama`/`azuresearch` extras' pattern) and implement `PdfDocumentLoader.load()` — no other file in this package needs to change. Real embeddings: implement a concrete `EmbeddingProvider`, add a vector field + `vectorSearch` configuration to `build_index_definition()`, and switch `AzureAISearchProvider.retrieve()` to a vector or hybrid query — a materially larger change deserving its own PBI and ADR, consistent with the "no vector search" exclusion's own review trigger. SharePoint: implement a new loader class satisfying the existing `DocumentLoader` Protocol (`matches`/`load`), doing its own Graph API fetch internally before returning the same typed `list[IngestionChunk]` — `KnowledgeIngestionPipeline` needs zero changes to accept it.

## 2026-08-07 — PBI-03-03: `content_hash` is a Pydantic `computed_field`, matching the established precedent

**Decision:** `IngestionChunk.content_hash` is declared with `@computed_field` + `@property`, not a plain `@property`. This repeats PBI-02-03's own corrected pattern for `GroundingMetadata.is_grounded` verbatim: a plain `@property` is silently excluded from `model_dump()`/`model_dump_json()` in Pydantic v2, which would have made `content_hash` invisible in `chunk_to_search_document()`'s output if that function had used `chunk.model_dump()` instead of explicit field access (it doesn't, but a future refactor easily could) — and, more immediately, `test_content_hash_is_present_in_serialized_output` would have caught the same class of bug PBI-02-03 found only via a live smoke test, this time via a unit test written with the lesson already learned.

**Deviation/status change:** None — proactively applying a lesson already recorded in `docs/sprint_02/decisions.md`, not a new correction.

**How to apply:** Any future derived field on a Pydantic model in this codebase that must appear in serialized output needs `@computed_field`, not a plain `@property` — this is now the second time this exact class of bug has been proactively avoided by referencing the prior PBI's decision.

## 2026-08-07 — PBI-03-04: `enablePrivateNetworking` is a single toggle, not per-resource flags

**Decision:** One Bicep param, `enablePrivateNetworking`, controls all of: the VNet/subnets/NSGs' existence, all four Private Endpoints' existence, all four Private DNS Zones' existence, each of the four services' `publicNetworkAccess`, and the Container Apps Environment's VNet integration. There is no way to enable networking hardening for, say, only Cosmos DB while leaving Azure OpenAI public.

**Deviation/status change:** None — a deliberate simplification matching this PBI's own framing ("harden the Azure runtime for production," not "harden individual resources independently"). A production environment gains nothing from a half-hardened network posture, and per-resource toggles would have multiplied the parameter surface and the number of untested combinations for no real benefit at this stage.

**How to apply:** If a future PBI needs finer-grained control (e.g., a resource that must stay public for a specific integration reason), split the single toggle into per-resource booleans at that point, defaulting all of them to the value `enablePrivateNetworking` currently controls — this preserves backward compatibility with today's two-state (`dev`=false, `staging`/`prod`=true) parameter files.

## 2026-08-07 — PBI-03-04: Container Apps ingress stays external in every environment, including prod

**Decision:** `containerAppsEnvironmentInternal` defaults to `false` in `main.bicep` and is left at that default in all three `.bicepparam` files (dev, staging, prod) — even though staging/prod otherwise enable full private networking. The Container Apps Environment's public ingress is therefore still reachable directly from the internet in every environment today.

**Deviation/status change:** None — a direct, necessary consequence of this PBI's own explicit exclusion of Application Gateway, Azure Firewall, and WAF ("these belong to future infrastructure PBIs"). Setting `internal=true` without a Front Door or Application Gateway in front would make the platform completely unreachable — a strictly worse outcome than the current, honestly-documented state.

**How to apply:** The future PBI that adds Azure Front Door or Application Gateway should, as one of its own last steps, flip `containerAppsEnvironmentInternal` to `true` in `staging`/`prod.bicepparam` (dev can reasonably stay external/simple) and verify the Front Door/Gateway becomes the only public entry point. See ADR-0002's "Container Apps ingress" section and its ADR-0002 review trigger for this exact scenario.

## 2026-08-07 — PBI-03-04: Key Vault gets `networkAcls.bypass: 'AzureServices'` alongside the public-access toggle

**Decision:** `key-vault.bicep`'s `networkAcls` block sets `bypass: 'AzureServices'` regardless of `enablePublicNetworkAccess`'s value, with only `defaultAction` toggling between `Allow`/`Deny`. This was not originally planned as part of the naive "add a public-access toggle to 4 modules" task — it was added after recognizing that `main.bicep` itself writes a secret into this vault (`modules/key-vault-secret.bicep`, the `appinsights-connection-string`) via a nested ARM template resource, and that operation needs to reach the vault's data plane through the ARM control plane even when `publicNetworkAccess: Disabled` is set.

**Deviation/status change:** A necessary correctness addition discovered during implementation, not scope creep — without it, `enablePrivateNetworking=true` would have compiled successfully (Bicep cannot catch this at compile time) but silently broken the App Insights secret write at actual deployment time, a gap that would only have surfaced during a real deployment this PBI was explicitly told not to perform.

**How to apply:** Any future Key Vault secret written via a Bicep-nested `Microsoft.KeyVault/vaults/secrets` resource (not this platform's own runtime `SecretProvider` code path, which already handles auth correctly) needs this same `bypass: AzureServices` setting to keep working once public network access is disabled — this is a general Azure IaC pattern, not specific to the App Insights secret.

## 2026-08-07 — PBI-03-04: dev keeps `enablePrivateNetworking=false` — both for cost and for Azure AI Search Free-tier compatibility

**Decision:** `dev.bicepparam` sets `enablePrivateNetworking = false`, matching the file's existing conservative-cost pattern (Free-tier AI Search, Serverless Cosmos, no Key Vault purge protection). This is a *doubly* justified choice: beyond cost, Azure AI Search's Free tier does not support Private Link at all — `aiSearchSkuName='free'` and `enablePrivateNetworking=true` together would fail at real deployment time, and dev is the only environment using the Free tier.

**Deviation/status change:** None — consistent with every prior per-environment sizing decision already recorded in this file and `docs/sprint_02/decisions.md`.

**How to apply:** If a future PBI ever needs dev to exercise the hardened network posture too, `aiSearchSkuName` must be bumped off `free` in that same change — the two params are coupled by a real Azure platform constraint, not just a stylistic choice, and this coupling is documented in `ai-search.bicep`'s own `enablePublicNetworkAccess` param description, `main.bicep`'s `enablePrivateNetworking` param description, and ADR-0002.

## 2026-08-07 — PBI-03-04: NSG rules are honest starting points, not a claimed deny-by-default lockdown

**Decision:** The two NSGs (`virtual-network.bicep`) add a small number of explicit ALLOW rules (health probes, HTTPS ingress, Private Endpoint access from the Container Apps subnet only) but do not add any explicit DENY rules overriding Azure's own default `AllowVnetInBound`/`AllowAzureLoadBalancerInBound` rules, which ARM does not allow removing. This means, for example, the private-endpoints subnet's explicit "allow 443 from the container-apps subnet" rule is, today, already implied by the broader default `AllowVnetInBound` rule — it exists to make the intended traffic pattern explicit and reviewable, not to actually restrict anything beyond what the defaults already allow.

**Deviation/status change:** None — an honest, self-aware scope boundary consistent with CLAUDE.md's own "never claim a feature... succeeded unless it was actually executed" principle, applied here to a security *claim* rather than a test result. This PBI's own instructions say "Apply NSGs where appropriate," which the NSGs satisfy; they do not say "achieve a fully deny-by-default network posture," which would require live testing this PBI could not perform (no Docker daemon, no real Azure deployment).

**How to apply:** A future, narrowly-scoped security-hardening PBI with the ability to actually deploy and test against real Azure resources should add explicit DENY rules (at a priority number between the custom ALLOW rules and Azure's 65000+ defaults) to make VNet-trust genuinely least-privilege rather than merely documented as an intent. Do not add such DENY rules speculatively without the ability to verify they don't break legitimate platform traffic (e.g. Container Apps' own internal control-plane communication).

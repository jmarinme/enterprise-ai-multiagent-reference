# Sprint 08 Decisions and Deviations

Record sprint-specific decisions and deviations. Cross-sprint decisions belong in ADRs.

## 2026-08-10 — PBI-08-01 (A-07): Retry/circuit-breaker classification per provider — never a blanket "retry everything"

**Decision:** `src/core/resilience/retry.py`'s `retry_with_backoff` retries only exception
*types* the caller explicitly names, optionally narrowed further by an `is_retryable`
predicate. Each provider's own classification, decided by reading its real exception mapping
before writing any wrapping code:

- **`AzureOpenAIProvider`**: retries `APIConnectionError`/`APITimeoutError`/`RateLimitError`
  only — never `APIStatusError`, which the OpenAI SDK uses for both retryable 5xx *and*
  non-retryable 4xx/content-filter outcomes without a distinguishing exception type. Rather than
  parse status codes out of an ambiguous exception, the conservative choice was to never retry
  it at all — a real 5xx from Azure OpenAI will not be retried by this layer, but it also will
  never accidentally retry a genuine bad-request/content-filter rejection.
- **`AzureAISearchProvider`**: retries `ServiceRequestError` only (a real transport-level
  failure) — never `ClientAuthenticationError` (config/credential issue, retrying can't help)
  or the generic `HttpResponseError` (same ambiguous-4xx-vs-5xx problem as above).
- **`CosmosConversationRepository`**: the one case where narrowing IS practical, since
  `CosmosHttpResponseError`/`ServiceRequestError`/`ServiceResponseError` all carry (or lack) a
  real `status_code` — retries only 408/429/500/503 via an explicit `is_retryable` predicate;
  404 (not found — a real, expected outcome `get_conversation`'s own caller relies on) and 409
  (conflict) are confirmed, by a dedicated test, to propagate on the first attempt.

**How to apply:** Any future external call this platform adds should classify its own
transient-vs-business exceptions the same deliberate way — read the SDK's real exception
hierarchy first, never assume "network-shaped exception = safe to retry" without checking
whether that same exception type also covers a genuine business outcome.

## 2026-08-10 — PBI-08-01 (A-07): Circuit breaker wraps the whole retry sequence, not each individual attempt

**Decision:** Every provider composes `circuit_breaker.call(lambda: retry_with_backoff(...))` —
the breaker only records ONE failure per logical operation (after retries are exhausted), not
one failure per retry attempt. This means a single transient blip that retry already smooths
over never counts toward the breaker's threshold; the breaker only trips on sustained,
retry-exhausted failure, which is the correct signal for "stop calling this dependency for a
while," not "this dependency hiccuped once."

**How to apply:** Do not invert this composition (retry wrapping the breaker) — that would let
the breaker's own OPEN-state fast-fail get retried pointlessly, defeating its purpose.

## 2026-08-10 — PBI-08-01 (A-08): `LLMProvider` gains `health_check()`; Cosmos/AI Search reuse existing methods instead — a deliberate asymmetry

**Decision:** Readiness needs a way to check each of the three external dependencies without
performing real, costly work. For Cosmos and Azure AI Search, the *existing* Protocol methods
(`ConversationRepository.list_conversations`/`KnowledgeRetriever.retrieve`) are already cheap
enough to reuse directly — a `list_conversations` for a reserved, synthetic partition key costs
the minimum possible RUs (an empty partition); a `retrieve` with `top_k=1` is a normal, cheap
search query. No new Protocol method was added for either. For the LLM, the equivalent
"cheapest real interface method" is `generate()` itself — invoking a real chat completion on
every readiness probe tick would cost real tokens/money and add real latency, unacceptable for
something Container Apps might poll every few seconds. `LLMProvider` therefore gained a new
Protocol method, `health_check()`, implemented per-provider with the cheapest real
introspection call each SDK actually offers (`client.models.list()` for Azure OpenAI, `GET
/api/tags` for Ollama, an unconditional `True` for the dependency-free Mock provider).

**Deviation/status change:** A small, deliberate asymmetry across the three provider
abstractions — not an oversight. Reusing existing methods for two of three keeps the change
smaller; the LLM case genuinely needed something new because its own primary method is the one
operation a readiness check must specifically avoid calling for real.

**How to apply:** If a future dependency's own primary interface method is ever too
costly/slow for a cheap readiness check (the same reasoning that applied to the LLM here),
follow the same pattern — add a dedicated, cheap `health_check()`-style method to that one
Protocol rather than reusing the expensive one.

## 2026-08-10 — PBI-08-01 (A-08): `/ready` never exposes an exception message, connection string, or endpoint URL

**Decision:** Every dependency check in `apps/api/src/api/routes/health.py` catches its own
failure broadly (`except Exception`) and reports only the fixed word `"unreachable"` — the real
exception's message text, which could contain an internal hostname, a partial connection
string, or SDK-internal detail, never reaches the HTTP response or is logged at anything above
`WARNING` with only a `dependency` tag (no message content). Verified by a dedicated test that
deliberately raises an exception containing a value that must never appear in the response body.

**How to apply:** Any future dependency check added to `/ready` must follow the same pattern —
catch broadly, report only a fixed status word, never format the caught exception into anything
user-visible.

## 2026-08-10 — PBI-08-01 (A-11): Container Apps `Replicas` metric for availability, not an Application Insights web test

**Decision:** Finding A-11 asks for "application availability/health" coverage. The
textbook Application Insights mechanism for this is a `Microsoft.Insights/webtests` availability
ping test (a URL probe from Azure's global test locations), but that resource type requires
hand-authored Visual-Studio-WebTest-format XML inside the Bicep template — real complexity and
schema risk for what this PBI asks to be "minimal"/"lightweight." Querying the real, already-
deployed `ca-tmxap-dev-api` Container App live (`az monitor metrics list-definitions`) confirmed
it already exposes a `Replicas` metric — alerting when average replica count drops below 1 over
a 5-minute window is an equally direct "the API cannot serve any request at all" signal, using
only the same simple `Microsoft.Insights/metricAlerts` resource type the other two alerts
already use (one schema to get right, not two).

**Deviation/status change:** A scope-appropriate simplification, not a lesser guarantee — zero
replicas is at least as strong an "unavailable" signal as a failed HTTP ping, and arguably
stronger (it doesn't depend on Azure's test-location infrastructure being healthy too).

**How to apply:** If a future need specifically requires testing full end-to-end HTTP
reachability (e.g., to catch an app that has replicas running but is deadlocked/unresponsive),
add a `Microsoft.Insights/webtests` resource at that point — this decision doesn't preclude it,
it just didn't justify the added complexity for this PBI's "minimal" requirement.

## 2026-08-10 — PBI-08-01 (A-11): Alert email address left empty by design — never an invented address

**Decision:** `alertEmailAddress` defaults to `''`, which creates the Action Group with zero
notification receivers — the alert rules still exist, still evaluate, and still show up in the
Azure Portal's Monitor/Alerts blade, but nobody is paged by email until a real operational
address is configured. No placeholder/invented email was hardcoded anywhere.

**How to apply:** Set `alertEmailAddress` in `dev.bicepparam` (or via
`--parameters alertEmailAddress=<real address>`) to a real, human-owned operational address
before this actually needs to page someone — a separate, explicit action, not done as part of
this PBI (CLAUDE.md §7.1: Claude Code does not deploy; and no real operational email address is
known to this session).

## 2026-08-10 — PBI-08-01 (A-11): Bicep validated, not applied — matches the CLAUDE.md §7.1 delivery model exactly

**Decision:** `az bicep build` (standalone module, then full template) and
`az deployment group validate`/`what-if` (against the real `rg-tmx-agent-platform-dev`) all
succeeded — confirming the new module is genuinely deployable, not merely locally plausible. No
`az deployment group create` was run. This is not a scope gap: CLAUDE.md §7.1 (Sprint 07)
established that Azure DevOps, not Claude Code, owns deployment once CI/CD is operational — this
PBI's own instructions repeat that ("Do not manually deploy DEV").

**How to apply:** The next real Azure DevOps pipeline run against `main` (once the
prerequisites in `docs/sprint_07/azure-devops-setup.md` are complete) will apply this change via
its own `InfrastructureDeploy` stage — no separate manual step should be taken here.

## 2026-08-10 — PBI-08-01 (A-17): Prompt-injection tests verify existing structural guarantees, not LLM jailbreak resistance

**Decision:** `tests/conversational/test_prompt_injection_and_security_scenarios.py`'s seven
scenarios all run against `MockLLMProvider` — a deterministic, content-agnostic provider that
never actually "reads" or "obeys" an instruction embedded in a message (CLAUDE.md architecture
principle #2: "the LLM is not the source of truth"). Testing whether a *real* LLM can be
jailbroken by a crafted prompt is not meaningful against this provider, and this platform's own
architecture already means a successful jailbreak of the LLM's *text generation* could not, by
itself, bypass a business decision — those are made by deterministic Tools, never the LLM. The
tests therefore verify the platform's real, structural guarantees instead: no internal
diagnostic/prompt/model-name leakage into the visible response (PBI-04-04's own diagnostic-
hiding work, reverified here under adversarial phrasing), no claimed-authority bypass of the
Tool-driven Claims flow, no crash on injection-shaped or oversized input, and no
header/body-content cross-contamination for the correlation ID.

**Deviation/status change:** None from this PBI's own instructions ("add prompt-
injection/security test scenarios") — interpreted as scenarios appropriate to this
architecture's actual attack surface, not a generic LLM red-team exercise this platform's design
already makes largely moot.

**How to apply:** If a live-Azure-OpenAI-backed prompt-injection assessment is ever wanted (a
genuinely different exercise — testing whether the real model can be steered into an
unauthorized *tool call request*, which `ToolCallingOrchestrator`'s own allow-list would then
have to block), that is a distinct, larger, live-validation PBI, not an extension of this one.

## 2026-08-10 — PBI-08-01 (A-17): Latency/cost telemetry — documented measurement, not new Supervisor/Agent code

**Decision:** `src/supervisor/orchestrator.py` already logs `supervisor_turn_latency`
(`contextLoadMs`/`agentHandleMs`/`persistMs`/`totalMs`, with `correlationId`) on every turn —
real evidence of this was captured from the new load test's own output
(`evidence/latency-and-cost-telemetry.md`). Token usage (`LLMUsage.prompt_tokens`/
`completion_tokens`/`total_tokens`) is already populated on every real `LLMResponse` by
`AzureOpenAIProvider.generate()` from the actual Azure OpenAI API's own `usage` field — but
nothing currently aggregates or logs it. Threading `LLMUsage` up from each Agent's internal
`llm_provider.generate()` call(s) into `AgentResponse` (so the Supervisor could log it alongside
`supervisor_turn_latency`) would touch every Agent's return contract — closer to the "redesign
conversation flows" boundary this PBI's own instructions explicitly rule out than to a
"lightweight" addition. **Chosen instead: document the existing mechanism and the cost-
computation methodology** (`evidence/latency-and-cost-telemetry.md`), exactly matching this
PBI's own explicit "or documented measurement" alternative.

**How to apply:** A future, separately-scoped PBI could add a `usage: LLMUsage` field to
`AgentResponse` (defaulting to zero-usage, additive/backward-compatible, matching this
codebase's own established pattern for extending that model — e.g. PBI-02-03's `citations`
field) and have the Supervisor log it — a real, moderate-sized, worthwhile follow-up, not
attempted here.

## 2026-08-10 — PBI-08-01 (Observability item 6): OpenTelemetry adoption assessed as non-trivial — documented recommendation, not implemented

**Decision:** Per this PBI's own explicit instruction ("If OpenTelemetry can be added cleanly
without broad refactoring, document the recommendation but do not expand scope into A-10 unless
trivial"), a real assessment was made before deciding not to implement it. A clean OTel adoption
would require: (1) new dependencies (`opentelemetry-api`/`sdk`, `opentelemetry-instrumentation-
fastapi`, an Azure Monitor OTLP exporter — `azure-monitor-opentelemetry`); (2) startup-time
instrumentation wiring in `apps/api/src/main.py` for FastAPI, `httpx`/the Azure SDKs'
own HTTP transports, and Cosmos/OpenAI/AI Search client instrumentation; (3) a real decision on
how the existing hand-rolled `correlationId` (a plain `ContextVar`, `apps/api/src/api/
middleware/correlation_id.py`) reconciles with OTel's own trace-ID/span-ID model — either
running both concepts in parallel (confusing, two IDs meaning almost the same thing) or
migrating every existing structured-log call site to read the trace ID instead (a genuine,
repository-wide refactor of the current logging architecture, which this PBI's own instructions
say not to replace "unless required"). None of this is trivial — it is a real, moderate/large
follow-up PBI, not a documentation-only or few-line change.

**Recommendation for that future PBI:** Adopt `azure-monitor-opentelemetry`'s distro package
(bundles the API/SDK/exporter/common auto-instrumentors in one dependency, Microsoft's own
documented recommended path for Application Insights migration off connection-string-only
ingestion) rather than assembling raw OTel SDK + exporter by hand; keep the existing
`correlationId` `ContextVar`/header contract unchanged for backward compatibility with any
external caller already relying on `X-Correlation-ID`, and additionally log the OTel trace ID
alongside it (both present, not a replacement) until every consumer has migrated; instrument
FastAPI and outbound HTTP automatically via the distro's auto-instrumentation rather than
hand-wrapping each Azure SDK call site.

**How to apply:** This is the concrete starting point for a future "PBI-0X-0X: OpenTelemetry
Adoption" — do not attempt it inside a hardening/remediation PBI like this one again; it
deserves its own scoped plan, dependency review, and live-validation pass.

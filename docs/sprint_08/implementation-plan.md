# Sprint 08 — Implementation Plan

## PBI-08-01: Architecture Review Remediation & Hardening

### Step 1 — A-16 first (trivial, unblocks a clean `git status` for everything else)

Removed the stray `tatus` file at the repo root; confirmed via `git ls-files` and a root
directory listing that no other accidental artifact exists alongside it.

### Step 2 — A-07 (Resilience)

Explored the three genuinely external call sites (`AzureOpenAIProvider.generate`,
`AzureAISearchProvider.retrieve`, `CosmosConversationRepository`'s four container operations)
and each one's existing typed-exception mapping, to classify exactly which underlying SDK
exceptions are transient (retry) versus a real business/client outcome (never retry) before
writing any code. Built `src/core/resilience/` (`retry_with_backoff`, `CircuitBreaker`) as
small, dependency-free, provider-agnostic primitives, tested in isolation first (11 unit tests),
then wired into each provider with its own conservative, documented exception classification.
Added integration tests per provider proving both the retry-then-succeed path and the
never-retry-a-business-error path.

### Step 3 — A-08 (Readiness)

Kept `/health` byte-for-byte unchanged. Added `/ready`, checking only dependencies actually
configured (in-memory/mock/local defaults have nothing to check). Added a minimal
`health_check()` method to the `LLMProvider` Protocol (implemented by all three concrete
providers) since a real LLM readiness check must never perform a real, costly completion call;
reused the *existing* `ConversationRepository.list_conversations`/`KnowledgeRetriever.retrieve`
methods for the other two dependencies rather than adding parallel health-check methods there
too — a deliberate asymmetry, explained in `decisions.md`. Verified the response body never
leaks an exception message via a dedicated test.

### Step 4 — A-11 (Monitoring)

Queried the real, already-deployed `appi-tmxap-dev`/`ca-tmxap-dev-api` resources
(`az monitor metrics list-definitions`) to confirm actual metric names before writing any Bicep
— avoided guessing. Chose Container Apps' own `Replicas` metric for the availability signal
over an Application Insights availability web test (which needs hand-authored XML test
configuration) — simpler, equally direct, "lightweight" as the PBI asks. Validated the new
module standalone (`az bicep build`), then the full template (`az bicep build`,
`az deployment group validate`, `az deployment group what-if`) against the real DEV resource
group — all non-mutating, no resource actually created.

### Step 5 — A-17 (Hardening evidence)

Prompt-injection scenarios: reused `tests/unit/api/test_chat.py`'s own TestClient-based,
MockLLMProvider-backed pattern exactly, writing scenarios that verify existing structural
guarantees (no diagnostic leakage, no fake-authority bypass, no crash on injection-shaped
input) rather than attempting to discover a novel LLM jailbreak (not meaningful against a
content-agnostic mock provider). Load test: an in-process, ASGI-transport `httpx.AsyncClient`
concurrency smoke test — no real server process, no real network hop, matching "lightweight."
Security scan evidence: re-ran Sprint 07's own `pip-audit`/`npm audit`/`detect-secrets` tooling
(not reimplemented) for a fresh, current-state result. Latency/cost telemetry: captured real
`supervisor_turn_latency` structured-log evidence from the load test run; documented the
token-usage/cost-computation methodology rather than adding new Supervisor/Agent code (would
require threading `LLMUsage` through every `AgentResponse` — a broader change than this PBI's
"do not redesign... conversation flows" boundary allows).

### Step 6 — Observability note (OpenTelemetry)

Assessed what a clean OTel adoption would actually require (new dependencies, startup
instrumentation wiring for FastAPI/httpx/Azure SDKs, correlation-ID/trace-ID reconciliation,
exporter configuration) and concluded it is not trivial — documented as a recommendation in
`decisions.md`, not implemented, per this PBI's own explicit scope boundary. Verified
correlation ID propagation is unaffected by every other change via a new, dedicated test.

### Step 7 — Validation and documentation

Ran the full backend regression only once implementation was stable (612 passed, 2 skipped) —
targeted test runs were used throughout development instead of repeated full-suite runs. Wrote
`docs/sprint_08/{README,decisions,validation}.md` and `evidence/` with real command output, not
summarized/assumed results.

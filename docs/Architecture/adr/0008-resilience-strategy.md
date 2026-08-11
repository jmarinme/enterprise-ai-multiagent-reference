# ADR-0008: Resilience Strategy — Retry with Backoff and Circuit Breaker at the Provider Layer

## Status

Accepted — retroactively documented 2026-08-10 (PBI-10-02). This decision has been implemented
since Sprint 08 (PBI-08-01, `src/core/resilience/`), wired into every external-call provider
(`AzureOpenAIProvider`, `AzureAISearchProvider`, `CosmosConversationRepository`), and is codified
in CLAUDE.md principle #9 ("Resilience is explicit"). This ADR is the first formal record of the
design rationale.

## Context

CLAUDE.md principle #9 requires explicit resilience — "use timeouts, retries with backoff,
idempotency, and circuit breakers where applicable" — for a platform whose core dependencies
(Azure OpenAI, Azure AI Search, Cosmos DB) are all external network calls, each capable of
transient failure (throttling, timeouts, brief service unavailability) independent of any bug in
this codebase. `reports/review/01_architecture_review.md` Finding A-07 flagged the pre-PBI-08-01
gap: no retry or circuit-breaker logic existed anywhere in the platform.

## Decision

### Retry policy — `retry_with_backoff` (`src/core/resilience/retry.py`)

A generic async helper, not tied to any specific SDK: exponential backoff with full jitter
(`random.uniform(0, delay)`, avoiding synchronized thundering-herd retries across concurrent
requests), a configurable `max_attempts` (3 in every current caller) and `max_delay_seconds`
cap (8.0s in every current caller). It retries **only** exception types the caller explicitly
names as `retryable_exceptions` — any other exception propagates unretried on the first attempt.
An optional `is_retryable` callback narrows further within an already-retryable exception type
(e.g., a Cosmos `CosmosHttpResponseError` is only actually retried for status codes
`{408, 429, 500, 503}` — never `404`/`409`/`400`/`401`/`403`).

### Circuit breaker — `CircuitBreaker` (`src/core/resilience/circuit_breaker.py`)

A lightweight, per-process, in-memory three-state breaker (`CLOSED`/`OPEN`/`HALF_OPEN`):

- `CLOSED`: normal operation, failures counted.
- `OPEN`: fails fast (`CircuitBreakerOpenError`) without attempting the downstream call at all,
  once `failure_threshold` consecutive failures have occurred (5, in every current caller).
- `HALF_OPEN`: derived automatically once `reset_timeout_seconds` (30.0s, in every current
  caller) has elapsed since opening — the next call is a single trial; success closes the
  circuit, failure reopens it immediately regardless of the configured failure threshold.

Explicitly **not distributed** across Container App replicas — the module's own docstring states
this is an intentional, documented scope boundary matching the platform's existing per-process
`@lru_cache` singleton pattern (Architecture Review Finding A-06): each provider adapter
constructs exactly one `CircuitBreaker` instance in its own `__init__`, living for that process's
lifetime.

### Provider isolation — each external-call provider owns its own retry/circuit-breaker instance

Resilience is wired independently into each of the three providers, never shared:

- `AzureOpenAIProvider` (`src/llm/azure_openai_provider.py`)
- `AzureAISearchProvider` (`src/rag/azure_ai_search_provider.py`)
- `CosmosConversationRepository` (`src/services/conversation_store/cosmos.py`)

A failure or an open circuit in one (e.g., Azure OpenAI throttling) has no effect on another
(e.g., Cosmos DB reads/writes continue normally) — there is no shared, global circuit breaker
that would let one dependency's degradation cascade into an unrelated one.

### Failure classification — retryable exceptions and status codes are provider-specific, never blanket

Each provider declares its own `_RETRYABLE_EXCEPTIONS` tuple and, where the exception type covers
both transient and non-transient outcomes, its own `_is_retryable_status` narrowing function:

- **Cosmos DB**: `CosmosHttpResponseError`/`ServiceRequestError`/`ServiceResponseError` are
  retryable exception *types*, but only status codes `{408, 429, 500, 503}` are actually retried
  — `404` (not found, a real outcome `get_conversation`'s own caller expects) and `409`
  (conflict) are deliberately excluded so a legitimate "this conversation doesn't exist yet" is
  never mistaken for a transient failure.
- **Azure AI Search**: only `ServiceRequestError` (pure transport-level failure) is retryable —
  narrower than Cosmos's set, matching this provider's own failure surface.
- **Azure OpenAI**: its own `_RETRYABLE_EXCEPTIONS` tuple (`src/llm/azure_openai_provider.py`)
  is likewise scoped to that SDK's transient failure types, independent of the other two
  providers' classifications.

No provider retries "everything" — a non-transient business/client error (bad request,
authorization failure, not-found) always propagates on the first attempt, per CLAUDE.md's own
"do not retry non-transient business errors" framing (`retry.py`'s module docstring).

### Composition — circuit breaker wraps the whole retry sequence, not each individual attempt

Every provider's internal resilience wrapper (e.g., `CosmosConversationRepository._resilient_call`)
calls the circuit breaker around the *entire* retry loop, not around each individual attempt:

```
circuit_breaker.call(lambda: retry_with_backoff(operation, ...))
```

This means a failure is only counted once toward the circuit breaker's threshold per logical
operation, regardless of how many retry attempts that operation internally made — the circuit
breaker tracks "is this dependency healthy overall," not "did this one HTTP call succeed."

### Recovery strategy

Recovery is automatic and time-based, requiring no manual intervention: once
`reset_timeout_seconds` elapses after a circuit opens, the next call is allowed through as a
trial (`HALF_OPEN`); a successful trial call closes the circuit and resets the failure count to
zero; a failed trial reopens it immediately. Combined with the retry layer's own backoff, a
transient blip recovers within the retry loop itself (no circuit trip at all); a sustained outage
trips the breaker, fails fast for `reset_timeout_seconds`, then self-tests for recovery without
any operator action.

## Why resilience is implemented at the provider layer instead of the business layer

- **Business logic should not need to know a dependency is degraded.** `ClaimsAgent`,
  `BrokerAgent`, and `CommercialIntakeAgent` call `ToolProvider`/`LLMProvider`/
  `ConversationRepository` methods and receive either a result or a propagated exception — they
  contain no retry loops, no backoff timers, and no circuit-breaker state of their own. Placing
  resilience here means every current and future caller of a given provider gets the same
  resilience guarantee automatically, without remembering to wrap each call site individually.
- **Failure classification requires provider-specific knowledge.** Only the Cosmos adapter knows
  that a `404` from `read_item` is a legitimate outcome rather than a transient failure; only the
  Azure OpenAI adapter knows which of its SDK's exception types represent throttling versus a
  malformed request. This classification is intrinsic to each provider's own failure surface —
  putting it in the business layer would require leaking SDK-specific exception types up through
  `ClaimsAgent`, which the provider-abstraction pattern
  ([ADR-0006](0006-provider-abstraction-pattern.md)) exists specifically to prevent.
- **One circuit breaker per dependency, not one per business flow.** A circuit breaker's purpose
  is to track the health of one specific downstream dependency. Since `ClaimsAgent`,
  `BrokerAgent`, and `CommercialIntakeAgent` may all call the same `LLMProvider` instance, placing
  the breaker at the provider layer means all three benefit from (and contribute to) the same
  accurate health signal for that one dependency — a business-layer breaker per Agent would
  fragment that signal into three independent, less accurate views of the same underlying
  dependency's health.
- **Testability.** Each provider's resilience wrapper is unit-testable in isolation (mocking the
  underlying SDK call), without needing to also exercise Agent conversation state or Tool routing
  logic — a business-layer implementation would entangle resilience testing with business-flow
  testing.

## Alternatives considered

- **A shared, global circuit breaker/retry policy across all providers.** Rejected: this would
  make one dependency's failures affect unrelated dependencies' availability (e.g., Azure OpenAI
  throttling incorrectly degrading Cosmos DB access), and would force a one-size-fits-all failure
  classification that does not fit each SDK's actual exception surface.
  See "Provider isolation" above.
- **Retry/circuit-breaker logic embedded in each Agent's business flow.** Rejected — see "Why
  resilience is implemented at the provider layer" above; this would duplicate the same retry
  loop across every Agent that calls a given provider and leak SDK-specific exception handling
  into business code.
- **A third-party resilience library (e.g., `tenacity`, `circuitbreaker`).** Rejected: the
  actual requirement (bounded exponential backoff with jitter; a simple three-state breaker) is
  small enough that a ~70-line in-house implementation is easier to audit and keep dependency-free
  than adopting a new library, consistent with CLAUDE.md §5's instruction not to add a dependency
  a PBI doesn't require. Revisit if resilience requirements grow materially more complex (e.g.,
  bulkheads, adaptive rate limiting).
- **A distributed/shared circuit-breaker state (e.g., backed by Redis).** Rejected: CLAUDE.md §4.3
  explicitly defers Redis until a measured performance requirement and its own ADR justify it; a
  per-process breaker is an accepted, documented scope boundary (Architecture Review Finding
  A-06) appropriate for this platform's current single-environment-class deployment.

## Consequences

- Positive: transient failures against Azure OpenAI, Azure AI Search, and Cosmos DB are now
  absorbed automatically rather than surfacing as user-visible errors on the first blip —
  directly resolving Architecture Review Finding A-07.
- Positive: a sustained outage in one dependency fails fast (via its own circuit breaker) rather
  than each caller separately re-discovering the outage through a full retry cycle each time,
  reducing load on an already-struggling dependency.
- Negative / accepted trade-off: circuit-breaker state is per-process, not shared across Container
  App replicas — under horizontal scale-out, each replica independently tracks and trips its own
  circuit, so the platform-wide "is this dependency healthy" view is approximate, not a single
  source of truth. Accepted per Architecture Review Finding A-06 as proportionate to this
  platform's current scale; revisit if replica count or traffic grows enough to matter.
- Retry attempts add latency to a request that ultimately fails (up to `max_attempts` x backoff
  delay) — bounded deliberately (3 attempts, 8s max delay) to avoid compounding a user-visible
  timeout.

## Relationship with other ADRs

- [ADR-0006](0006-provider-abstraction-pattern.md) — resilience is wired inside each concrete
  provider implementation, behind the same Protocol boundary that pattern establishes; swapping a
  provider's backend does not change how resilience is applied to it.
- [ADR-0004](0004-conversation-store-selection.md) — `CosmosConversationRepository`'s specific
  retryable-status-code classification is one concrete application of this ADR's general
  strategy.

## Review triggers

- If Container App replica count grows enough that per-process circuit-breaker fragmentation
  becomes operationally significant — consider a shared state store at that point (with its own
  ADR, per CLAUDE.md §4.3's Redis-deferral condition).
- Before adding a fourth external-call provider — apply the same per-provider retry/circuit-
  breaker wiring pattern documented here, with its own failure classification.
- If observed retry/circuit-breaker behavior in a live environment (via Application Insights)
  shows the current thresholds (3 attempts, 5-failure trip, 30s reset) are miscalibrated for real
  traffic patterns.

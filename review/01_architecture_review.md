# 01 — Solution Architecture Review

## 2a. Architecture style & patterns

**Style**: a clean layered/hexagonal-leaning monolith — one deployable FastAPI service
(`apps/api`) that imports a reusable domain library (`src/`) — fronting a Supervisor→Agent→Tool
pipeline, with an optional Azure Functions execution path behind a Protocol seam
(`src/core/tool_provider/`, `src/core/workflow_provider/`) that is off by default
(`TOOL_PROVIDER=inprocess`, `CLAIMS_WORKFLOW_PROVIDER=inprocess`, `deployServerlessToolLayer=false`
— all three confirmed live on the DEV Container App during this review).

This is appropriate for the stated purpose (an academic reference implementation demonstrating a
production-shaped pattern, CLAUDE.md §1) and is **not** a naive monolith: routing (`src/supervisor/`),
business orchestration (`src/agents/`), and deterministic execution (`src/tools/`,
`src/services/tools/`) are genuinely separate, Protocol-bounded layers — verified, not just
claimed, by reading `src/supervisor/orchestrator.py` (depends only on `ConversationRepository`,
`IntentResolver`, `AgentRegistry` Protocols — zero imports of a concrete Agent) and every Agent's
constructor (depends only on `ToolProvider`/`ToolExecutor`, `PromptManager`, `LLMProvider`
Protocols — never a concrete Tool implementation).

**Anti-patterns checked for and not found**: no God object, no circular imports observed across
the layers read, no direct database access from an Agent (CLAUDE.md principle #4, verified: every
business fact flows through a typed Tool call, e.g. `src/agents/claims/workflow.py`'s
`_handle_validating_policy` calling `tool_provider.execute(ToolRequest(tool_name="policy_lookup",
...))`, never a repository/ORM call).

**Domain model**: present but intentionally thin — `src/domain/conversation.py` (Conversation,
Message) is the only persisted domain model; each Agent's own working-state model
(`ClaimsIntakeState`, `BrokerInquiryState`, `CommercialIntakeState`) is explicitly documented as
*not* core business truth (CLAUDE.md §4.3) but in-progress session notes. This is a deliberate,
well-reasoned choice (see `src/agents/claims/state.py`'s own docstring), not scattered logic —
each state machine is a single dict-dispatched handler table, not an if/elif chain.

## 2b. Scalability & performance

- **No N+1 query pattern found** — there is no ORM/SQL layer at all; Cosmos DB access
  (`src/services/conversation_store/cosmos.py`) is a single partition-scoped read/write per
  conversation turn, and every synthetic Tool (`src/services/tools/*.py`) is an in-memory dict
  lookup.
- **Async I/O throughout**: every provider/repository method is `async def`; verified no blocking
  `time.sleep()`/`requests.*` call exists in request-path code (`src/core/resilience/`,
  `src/supervisor/orchestrator.py` only use `time.monotonic()`/`time.perf_counter()` for
  measurement, never blocking).
- **Horizontal scaling — a real, structural limitation**: dependency wiring in
  `apps/api/src/api/dependencies.py` uses `@lru_cache` extensively (12 occurrences) to build
  per-process singletons (registries, providers, the Supervisor itself). This is fine within one
  process/replica but means any in-memory state (`InMemoryConversationRepository`, the
  `CircuitBreaker` instances themselves) does **not** share across replicas — scaling the
  Container App beyond `minReplicas=1`/`maxReplicas=1` (confirmed via `az containerapp show`,
  `scale.maxReplicas: 1` today) would need either sticky sessions or acceptance that
  circuit-breaker state and (if `CONVERSATION_STORE_PROVIDER` were ever left at its in-memory
  default in a real multi-replica deployment) conversation history would not be shared. This is
  the same pre-existing, documented characteristic the prior review flagged (its own finding
  A-06) — still true, not yet addressed, and now slightly more consequential since a genuine
  resilience layer (circuit breakers) has been added on top of the same per-process assumption.
- **Caching**: no HTTP response cache, no read-through cache for Tool lookups — reasonable, given
  every Tool call is already an in-memory dict lookup with negligible cost; nothing here would
  benefit from caching today.

## 2c. Resilience & reliability — materially improved since the prior review

- **Retry + circuit breaker now exist** (`src/core/resilience/retry.py`,
  `circuit_breaker.py`), and are wired into all three genuinely external-call providers:
  `AzureOpenAIProvider`, `AzureAISearchProvider`, `CosmosConversationRepository` (confirmed by
  reading each provider's own resilience-wrapped call site in earlier work this session).
  `retry_with_backoff` distinguishes retryable transport failures from non-retryable
  auth/4xx errors per-provider — a conservative, correct design (not "retry everything").
- **External failure handling**: each provider degrades to a typed exception the calling Agent's
  broad-catch boundary already converts into a safe, generic user-facing message
  (`_SAFE_FALLBACK_MESSAGE` in every `*_agent.py`) — verified this pattern is consistent across
  Claims/Broker/Commercial.
- **Graceful degradation**: RAG retrieval failure (`KnowledgeError`) never blocks the
  deterministic business flow (`ClaimsAgent._retrieve_knowledge`'s own try/except, degrading to
  an empty chunk list) — a good, explicit example of "AI-adjacent capability failing open, never
  blocking business logic," consistent with CLAUDE.md principle #1.
- **Health checks**: `/health` (unconditional liveness) and **`/ready`** (dependency-aware
  readiness, added since the prior review — checks only whatever is actually configured:
  LLM provider health, conversation repository, knowledge retriever) both exist
  (`apps/api/src/api/routes/health.py`). This closes the prior review's own liveness-only gap.
- **Remaining gap**: no timeout is explicitly set on the Azure OpenAI/Cosmos/AI Search SDK client
  calls beyond each SDK's own default — not independently verified as a problem (SDK defaults are
  usually reasonable), but also not confirmed as deliberately tuned.

## 2d. Observability

- **Structured logging**: JSON logs with `correlationId`, consistent level usage
  (`apps/api/src/observability/logging.py`), confirmed live in this review's own deployment
  validation (every `supervisor_turn_latency` log line carried a real correlation ID end to end).
- **Correlation ID propagation**: `CorrelationIdMiddleware` + a context var threaded through
  Supervisor → Agent → Tool → response header — independently re-verified live in this review
  (`X-Correlation-ID` sent in, same value returned in the response header, confirmed via `curl`
  against the real DEV API during this session's own deployment validation).
- **Metrics/APM**: Application Insights is provisioned and wired (the
  `APPLICATIONINSIGHTS_CONNECTION_STRING` env var, confirmed present on the live Container App);
  no OpenTelemetry SDK is present in either `pyproject.toml` — CLAUDE.md §5 names OpenTelemetry
  specifically, so this remains a partial stack drift (App Insights auto-instrumentation may
  cover some of this gap in practice, but was not verified).
- **Alerting — new since the prior review**: `ops/bicep/modules/monitor-alerts.bicep` provisions
  one Action Group and three metric alerts (error rate, latency, availability), confirmed live via
  `az resource list` in this review (`ag-tmxap-dev-ops`, `alert-tmxap-dev-error-rate`,
  `alert-tmxap-dev-high-latency`, `alert-tmxap-dev-availability`, all `Succeeded`). This closes
  the prior review's "no alerting" finding.

## 2e. Data architecture

- **No relational schema** — Cosmos DB (NoSQL, single container, `/userId` partition key) and a
  small set of in-memory synthetic dicts are the only "data model." Normalization concerns don't
  apply in the traditional sense; the partition-key choice is sound for the access pattern
  (always query by `userId`).
- **Migration strategy**: still not defined for Cosmos DB schema evolution (same as prior
  review) — low urgency today given the small, append-only conversation-history shape, but worth
  a short ADR before any real schema change.
- **PII/sensitive data**: none exists by design — every business record is explicitly synthetic
  and labeled as such (`SYN-*`/`CUS-SYN-*` prefixes throughout
  `src/services/tools/synthetic/provider.py`). `userId` itself is the only quasi-identifier, and
  it is unauthenticated (see `02_security_review.md` for the resulting IDOR).

## 2f. Technical debt & maintainability

- **Zero `TODO`/`FIXME`/`HACK` comments** found anywhere in `src/`, `apps/api/src/`,
  `apps/web/src/` — an unusually clean signal, consistent with the prior review's own finding and
  still true today despite ~4,200 more lines of code since.
- **DRY**: shared logic is consistently extracted once genuinely duplicated across ≥2 call sites
  (e.g. `src/agents/shared/state_persistence.py`, `messages.py`, `memory.py`) rather than
  speculatively — matches CLAUDE.md §7's own "no premature abstraction" instruction, and the
  project's own sprint decision logs show this reasoning being applied deliberately (e.g.
  `docs/sprint_01/decisions.md`'s documented refusal to share a base class between the three
  Agents until a third one actually needed it).
- **Cohesion/coupling**: each Agent module (`src/agents/claims/`, `broker/`, `commercial/`) is a
  self-contained `state.py`/`extraction.py`/`workflow.py` triad with no cross-imports between
  domains — verified by grep (no `from src.agents.broker` import anywhere under
  `src/agents/claims/`, and vice versa).
- **Navigability**: the 9 sprint READMEs plus per-sprint `decisions.md`/`validation.md` give a
  genuinely traceable history of *why* each design choice was made — better documentation
  discipline than most production codebases this reviewer has seen, academic or otherwise.
- **One real structural debt item, newly surfaced by this review**: the memory-prefill gating
  logic in `claims_agent.py`/`broker_agent.py`/`commercial_intake_agent.py` (PBI-09-01) is
  correct but per-Agent-bespoke — each Agent's `_prefill_from_memory` independently reasons about
  which fields are safe to re-apply every turn vs. only on first entry. This is well-justified
  per-Agent (documented in each file's own docstring and `docs/sprint_09/decisions.md` D-07) but
  is exactly the kind of repeated-reasoning-across-three-similar-modules pattern that, if a
  fourth domain Agent is ever added, should prompt extracting the general rule rather than
  copying the pattern a third time — flagged here as a forward-looking maintainability note, not
  a current defect.

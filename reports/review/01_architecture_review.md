# 01 — Solution Architecture Review

Reviewer persona: Solution Architect. Scope: does the code match the stated
Web → API → Supervisor → domain Agents → Tools/RAG → Cosmos design; scalability; resilience;
observability; data architecture; technical debt.

## 2a. Architecture style & patterns

**Finding A-01 (positive control, verified — not a gap):** The stated layering is real, not
aspirational. Verified by direct code inspection, not just documentation:

- `apps/api/src/api/routes/chat.py:52-75` — `post_chat()` contains zero business logic; it maps
  `ChatRequest` → `AgentRequest`, calls `supervisor.handle()`, maps the result back. The route's
  own docstring (`chat.py:1-6`) states this intent and the code matches it.
- `src/supervisor/orchestrator.py:41-109` — `SupervisorOrchestrator` depends only on
  `ConversationRepository`, `IntentResolver`, `AgentRegistry` (all Protocols, constructor-
  injected at `orchestrator.py:53-63`). `grep`-level check: no `from src.agents` or
  `from src.services.tools` import anywhere in `src/supervisor/*.py`.
- `apps/api/src/api/dependencies.py:1-9` — explicitly documented, and actually structured, as
  the **single composition root**: it is the only file importing concrete `ClaimsAgent`,
  `BrokerAgent`, `CommercialIntakeAgent`, and all 14 concrete Tool classes
  (`dependencies.py:16-51`). `src/supervisor/`, `src/tools/`, `src/prompts/`, `src/llm/` never
  import a concrete implementation of their own abstraction — verified for `src/supervisor/` by
  grep; consistent with the same pattern documented and tested for the other frameworks per
  Sprint 01/02 acceptance criteria (`docs/sprint_01/README.md` AC-01, AC-07, AC-10, AC-13).
- Tool authorization is a real, enforced boundary, not just a naming convention:
  `src/core/tool_calling/orchestrator.py` (per `docs/sprint_02/README.md` PBI-02-04 writeup)
  checks an LLM-requested tool against `ToolRegistry` existence *and* the calling Agent's
  allow-list *before* `ToolExecutor` ever runs — an unauthorized or unknown tool name fails
  safely with typed data, not a stack trace or a silent execution.

This is a genuinely clean hexagonal/ports-and-adapters style applied consistently five times
(Supervisor, Tools, Prompts, LLM, RAG/Knowledge) — each framework has its own Protocol, its own
typed exception hierarchy, and its own composition-root wiring point. For an academic reference
implementation whose explicit second goal is reusability (CLAUDE.md §1), this consistency is the
single strongest architectural asset in the codebase.

**Finding A-02 (anti-pattern, minor):** Import style is inconsistent at the API-route boundary.
`apps/api/src/api/routes/chat.py:13-16` imports `src.core.tool_calling.models`,
`src.rag.grounding_models`, `src.supervisor.models`, `src.supervisor.orchestrator` all with the
`src.` prefix, while `apps/api/src/api/dependencies.py:16-51` imports the exact same tree
(`src.agents.*`, `src.tools.*`, `src.config.settings`) also with the `src.` prefix — but
`apps/api/src/main.py:6-9` imports its **own** sibling modules (`api.middleware...`,
`api.routes...`, `config.settings`, `observability.logging`) *without* any prefix. This is a
deliberate, documented consequence of the Dockerfile's dual-import-path design
(`apps/api/Dockerfile:6-10`: `apps/api/src` copied to `/app/app_src` and imported bare via
`--app-dir`; repo-root `src/` copied to `/app/src` and imported as `src.*` via `PYTHONPATH`) —
not an accident, and it works, but it means `apps/api`'s own code lives in two different Python
import namespaces simultaneously (`config` the local module vs. `src.config` the domain-library
module, both real, both imported in different files). This is a legitimate but unusual pattern
that a new contributor would need the Dockerfile comment to understand; it increases onboarding
friction without a corresponding architectural benefit that a single, consistent `src.`-prefixed
namespace wouldn't also provide.

**Finding A-03 (drift from CLAUDE.md §4.1/§5, documented conditions apply):** Two stack elements
CLAUDE.md specifies are not actually used:

- **Azure Functions** for deterministic Tools (§4.2, §5): all 14 Tools run in-process inside the
  FastAPI app (`src/services/tools/*.py`, invoked via `src/tools/executor.py`). No
  `function_app.py`/`host.json` exists anywhere in the repository.
- **Durable Functions** for long-running Claims workflows (§4.1: "Claims Agent... delegates
  long-running processes to Durable Functions"): the Claims intake flow is a synchronous,
  in-process, dict-dispatched state machine (`src/agents/claims/state.py`, per
  `docs/sprint_01/README.md` PBI-01-05).

Neither is flagged as an explicitly-deferred item in any sprint's `README.md`/decisions the way
Entra ID or Redis are — this looks like an organic architectural substitution (a simpler
in-process design was built and it worked, so Functions/Durable Functions were never revisited)
rather than a deliberate, ADR-documented deviation. Functionally this is a reasonable choice for
a synthetic, low-volume academic demo — the current design is simpler, has fewer moving parts,
and every Tool call is still deterministic, versioned, and typed (satisfying principle #4's
actual intent) — but it is a real gap against CLAUDE.md's own explicit component inventory, and
per CLAUDE.md §1 ("If code or a sprint instruction conflicts with the architecture document,
stop, report the conflict, and propose the smallest compliant correction") this should be
reconciled with an ADR (either adopt Functions for Tools, or amend §4.2/§5 to reflect the
in-process design as the accepted pattern) before this platform is treated as architecture
ground truth for a real build-out.

## 2b. Scalability & performance

**Finding A-04 (positive):** Async I/O is used consistently at the boundaries that matter.
`post_chat()` (`chat.py:53`), `SupervisorOrchestrator.handle()` (`orchestrator.py:65`), every
`ConversationRepository` method, `LLMProvider.generate()`, and `KnowledgeProvider.retrieve()`
are all `async def`. No blocking `requests`/`time.sleep` call was found in the reviewed source
files (Cosmos, Azure OpenAI, AI Search, and Ollama providers all use `aiohttp`/async SDK
clients, per the Sprint 00/01/03 deliverable logs' own descriptions of `DefaultAzureCredential`
+ `aiohttp` usage).

**Finding A-05 (real gap, moderate):** No caching layer of any kind exists — not just Redis
(explicitly, correctly deferred per CLAUDE.md §4.3: "Redis is not part of Sprint 0. Add it only
when an ADR and measured performance requirement justify it" — this is a documented, accepted
gap, not a finding). But there is also no in-process caching for repeatedly-fetched data (e.g.
`LocalKnowledgeProvider` re-scores its keyword index from the same 5 Markdown documents on every
single call; `FileSystemPromptProvider` re-reads and re-parses prompt files from disk on every
render, per its own name). For the current synthetic-data, low-volume, single-instance DEV
deployment this has no observable impact, but there is no measured evidence in
`docs/sprint_04/decisions.md`'s own latency-logging work (`orchestrator.py:88-99`,
`contextLoadMs`/`agentHandleMs`/`persistMs`) that per-agent LLM/Tool/RAG latency was ever broken
down further — the sprint's own retrospective (`docs/sprint_04/README.md` AC-41) explicitly
scopes this out as a "legitimate follow-up," which this review concurs with.

**Finding A-06 (horizontal-scaling readiness, real gap):** `apps/api/src/api/dependencies.py`
uses `@lru_cache` (e.g. `dependencies.py:67-98,101-111,114-132,135-142,145-158,161-175,178-183,
186-239`) to build every framework singleton (registries, executors, providers, the Supervisor
itself) once per **process**. Combined with `InMemoryConversationRepository`/
`InMemoryToolRegistry` being the local/dev defaults, this means: (a) horizontal scale-out beyond
one Container App replica requires the Azure-backed providers (Cosmos, real LLM) to actually be
selected — which is already true in DEV (`CONVERSATION_STORE_PROVIDER=cosmos`,
`LLM_PROVIDER=azure_openai` per `docs/sprint_03/README.md` PBI-03-02) — and (b) there is no
in-memory cross-request mutable state that would break correctness under multiple replicas
*once Cosmos is selected*. This is architecturally sound for the DEV configuration actually
deployed; the risk is purely that the **default** local/test configuration
(`CONVERSATION_STORE_PROVIDER=in_memory`) is silently non-scalable, which is fine for local dev
but is worth an explicit comment/guard so a future environment promotion doesn't accidentally
ship the in-memory default.

## 2c. Resilience & reliability

**Finding A-07 (real gap against CLAUDE.md principle #9):** CLAUDE.md §3's tenth architecture
principle states: "Resilience is explicit — use timeouts, retries with backoff, idempotency, and
circuit breakers where applicable." A repository-wide search
(`grep -rniE "retry|backoff|circuit_breaker|idempot" src/`) found only 3 incidental matches
(`src/agents/broker/workflow.py`, `src/pipelines/knowledge_ingestion/pipeline.py`,
`src/services/tools/adjuster_assignment_tool.py` — none of which implement an actual retry/
backoff/circuit-breaker mechanism; they are unrelated uses of similar words, e.g.
"idempotent"-style duplicate-prevention business logic, which is a different concept from
transport-level retry). **Timeouts** are present (`LLMGenerationSettings` has a bounded timeout
field per `docs/sprint_01/README.md` PBI-01-04's AC), but no retry-with-backoff wrapper or
circuit breaker exists around any external call — Azure OpenAI, Cosmos DB, or Azure AI Search.
A transient Azure OpenAI 429/503 today propagates as a single failed call with no automatic
retry. This is a genuine, unaddressed gap against the project's own explicitly stated principle,
not a documented, scoped-out deferral like Entra ID or Redis — no sprint's `decisions.md`
discusses or defers retry/circuit-breaker design. **Blocking for a real production deployment**
handling live traffic against Azure OpenAI's real rate limits.

**Finding A-08 (health check is liveness-only, no dependency check):**
`apps/api/src/api/routes/health.py:8-11` returns a static `{"status": "ok"}` unconditionally —
it never checks Cosmos DB, Azure OpenAI, or Azure AI Search reachability. This is a legitimate
design choice *if* it is deliberately scoped as a liveness probe (Container Apps distinguishes
liveness vs. readiness), but there is no separate readiness endpoint, and no sprint doc discusses
this distinction. Practical consequence: Container Apps' health probe (and the CI pipeline's own
`SmokeTests` stage, `azure-pipelines.yml:463-502`) can report the API as healthy while its
Cosmos/Azure OpenAI connectivity is broken — the smoke test's `POST /chat` call partially covers
this (it exercises the full path), but the container's own health probe does not.

## 2d. Observability

**Finding A-09 (positive, verified end-to-end):** Correlation ID propagation is real, not just
documented. `apps/api/src/api/middleware/correlation_id.py:15-29` reads or generates an
`X-Correlation-ID` header, sets it on a `ContextVar`
(`observability.logging.correlation_id_ctx_var`), attaches it to `request.state`, and echoes it
back on the response. `src/supervisor/orchestrator.py:88-99` logs a structured
`supervisor_turn_latency` event carrying `correlationId`, `conversationId`, `agent`, and
per-phase timings — this is genuine, log-line-level evidence that the correlation ID reaches the
domain layer, not just the transport layer. `docs/sprint_03/README.md` PBI-03-06's Deliverable
Log entry additionally confirms (live-validated) that a WARNING log for the `gpt-5-mini`
temperature-capability gap carries the request's `correlationId` automatically. This satisfies
CLAUDE.md §7/§10's correlation-ID requirement concretely, with live evidence, not just code
review.

**Finding A-10 (gap, moderate):** CLAUDE.md §5 lists OpenTelemetry as the observability SDK.
`grep` for `opentelemetry` across both `pyproject.toml` files and `apps/api/Dockerfile` returns
no matches — the actual implementation is hand-rolled structured JSON logging plus Application
Insights/Log Analytics provisioned in Bicep (`ops/bicep/modules/app-insights.bicep`,
`log-analytics.bicep`), not the OpenTelemetry SDK itself. App Insights can still ingest
structured logs without the OTel SDK, so this is not a functional gap for the current design,
but it is a stack-inventory drift worth reconciling (either adopt the OTel SDK for standardized
distributed tracing spans across agent/tool boundaries, or update CLAUDE.md §5 to reflect the
structured-logging-only approach actually built).

**Finding A-11 (gap):** No alerting configuration (Azure Monitor alert rules, action groups) was
found anywhere in `ops/bicep/modules/` (15 module files listed; none named `alert`/
`action-group`/`monitor-alert`). Telemetry is collected (App Insights + Log Analytics
provisioned) but nothing appears wired to notify a human on failure — a real operational gap for
any environment beyond manual, human-driven DEV validation.

## 2e. Data architecture

**Finding A-12 (positive, matches CLAUDE.md §4.3 exactly):** `Conversation`/`Message` are typed
Pydantic models with `/userId` as the Cosmos partition key
(`ops/bicep/modules/cosmos-db.bicep`, per `docs/sprint_00/README.md` PBI-00-05), and — critically
— core business truth (policies, claims, brokers, payments, commissions) is never written to
Cosmos; it lives only in the synthetic in-memory provider
(`src/services/tools/synthetic/provider.py`) behind Tool abstractions. This directly satisfies
CLAUDE.md §4.3's "Core insurance truth must never be stored in Cosmos DB as authoritative..."
requirement — verified by inspecting what `ConversationRepository`'s write paths actually persist
(`Conversation`/`Message` only, `src/domain/conversation.py`, per the models referenced in
`orchestrator.py:117-149`).

**Finding A-13 (real gap, low severity given synthetic-only scope):** No migration strategy
exists for the Cosmos container schema — no versioned schema/migration tooling, no `schemaVersion`
field observed on `Conversation`/`Message`. For a low-volume, synthetic-data academic project this
is low-impact today, but it is a real gap that would need addressing before any real conversation
data (even under a future Entra ID identity) is stored.

**Finding A-14 (verified — no PII/real-data patterns found):** A full scan of `src/services/
tools/synthetic/provider.py` and `configs/knowledge_base/` found only clearly-labeled fabricated
names ("Synthetic Test Holder A/B", "Synthetic Adjuster A", "Synthetic Brokerage A/B") and
`SYN-*`/`CUS-SYN-*` identifiers — no real names, addresses, SSN/tax-ID-shaped strings, phone
numbers, or email patterns. Consistent with CLAUDE.md §2/§7's synthetic-data mandate.

## 2f. Technical debt & maintainability

**Finding A-15 (positive, notable):** `grep -rniE "TODO|FIXME|HACK|XXX" apps/ src/` (excluding
`.venv`) returns **zero matches**. For a 201-file Python codebase built across 6 sprints, this is
unusually clean — consistent with the sprint documentation's own practice of resolving or
explicitly deferring every known gap in a sprint's `decisions.md`/`README.md` rather than leaving
inline markers. This is a genuine maintainability strength: nothing is silently deferred in code
comments where it could be missed.

**Finding A-16 (minor hygiene issue):** A stray tracked file, **`tatus`**, sits at the repository
root (see `00_project_inventory.md` §4). It contains a dumped `git diff` transcript, not source
code or documentation — almost certainly the accidental result of a truncated shell redirect
(e.g. `git s... > tatus`). It is dead weight, not a security issue (no secrets in it), but its
presence at the repo root — alongside `CLAUDE.md`, `README.md`, `pyproject.toml` — is the kind of
thing a `git status` review before committing should have caught. Low severity, trivial fix
(`git rm tatus`).

**Finding A-17 (drift from Sprint 05's own planned scope, CLAUDE.md §14):** CLAUDE.md §14 defines
Sprint 05 as "Hardening and final evidence: Security and prompt-injection testing, dashboards,
cost telemetry, load/resilience tests, final documentation, academic evidence, and architecture
review." The Sprint 05 actually executed (`docs/sprint_05/README.md`) has a different objective:
"Intelligent Conversational Experience" — natural-language extraction, LOB-aware Claims, expanded
synthetic demo data. This is documented and self-consistent (Sprint 05's own README states its
real objective plainly, it is not hidden), but it means **the hardening work CLAUDE.md's own
sprint sequence calls for has not been executed under any sprint label yet** — no dedicated
prompt-injection test suite, no cost-telemetry dashboard, no load/resilience test evidence exists
anywhere in the repository as of this review. This is the single most consequential architecture-
level finding for a go/no-go decision: it is not that hardening was attempted and found wanting,
it is that the hardening sprint itself has not yet happened.

## Summary — architecture review

| # | Finding | Severity | Type |
|---|---|---|---|
| A-01 | Layering genuinely matches Web→API→Supervisor→Agents→Tools/RAG→Cosmos, verified in code | — | Positive |
| A-02 | Inconsistent import namespace at API boundary (`src.` prefix vs. bare) | Low | Anti-pattern (minor, deliberate tradeoff) |
| A-03 | Azure Functions / Durable Functions specified in CLAUDE.md §4/§5 not implemented; Tools/Claims workflow run in-process instead | Medium | Architecture drift, undocumented as a deviation |
| A-04 | Async I/O used consistently at all reviewed boundaries | — | Positive |
| A-05 | No caching layer beyond the explicitly-deferred Redis; no per-agent latency breakdown | Low | Documented follow-up |
| A-06 | `@lru_cache` per-process singletons + in-memory default providers — fine for current DEV config (Cosmos/Azure OpenAI selected), risky if the in-memory default were ever promoted | Low | Latent risk |
| A-07 | No retry-with-backoff or circuit breaker anywhere, despite CLAUDE.md principle #9 | High | Real, unaddressed gap |
| A-08 | `/health` is a static liveness-only probe, no downstream dependency check | Low | Gap |
| A-09 | Correlation ID propagation verified real end-to-end, live-validated | — | Positive |
| A-10 | OpenTelemetry (CLAUDE.md §5) not actually used; structured logging + App Insights used instead | Medium | Stack drift |
| A-11 | No Azure Monitor alerting/action groups found in Bicep | Medium | Operational gap |
| A-12 | Core business truth correctly never persisted to Cosmos; partition key/model match CLAUDE.md §4.3 | — | Positive |
| A-13 | No Cosmos schema migration strategy | Low | Gap (low impact, synthetic data only) |
| A-14 | No real PII/customer-data patterns found anywhere | — | Positive (verified) |
| A-15 | Zero TODO/FIXME/HACK markers across 201 Python files | — | Positive |
| A-16 | Stray `tatus` file committed at repo root | Low | Hygiene |
| A-17 | CLAUDE.md §14's Sprint 05 "Hardening" scope (security/prompt-injection testing, dashboards, cost telemetry, load tests) has not been executed under any sprint yet | High | Real, undone work — most consequential architecture finding |

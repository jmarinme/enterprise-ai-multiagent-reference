# 04 — Risk Register

Sorted by Risk Score descending within each status group. Scoring rubric: CRITICAL×HIGH=10,
HIGH×HIGH=8, HIGH×MEDIUM=6, MEDIUM×HIGH=5, MEDIUM×MEDIUM=3, LOW×any=1–2 (2 used where the
underlying issue is more consequential despite low likelihood, 1 otherwise).

## Open findings

RISK-001 ("No authentication exists on any API endpoint") and RISK-002 ("IDOR — any caller can
read another user's full conversation history") — the two highest-scored findings in the prior
version of this register — are **resolved**. See the Resolved findings section below
(RISK-025, RISK-026) for the full before/after evidence trail.

### RISK-003
- **Category**: Security
- **Title**: No rate limiting; unbounded request message length
- **Description**: Any caller can send unlimited, arbitrarily large `POST /chat` requests, each
  triggering a real (billed) Azure OpenAI call. Crude DoS and cost-exhaustion surface.
- **Evidence**: `apps/api/src/api/routes/chat.py` (`message: str`, no `max_length`); no rate-limit
  middleware found anywhere; `tests/conversational/test_prompt_injection_and_security_scenarios.py::test_extremely_long_message_does_not_crash_or_hang`
  explicitly documents "no new size limit was added."
- **Severity**: MEDIUM | **Likelihood**: MEDIUM | **Risk Score**: 3
- **Recommendation**: Add `Field(max_length=...)` to `ChatRequest.message`; add a basic
  per-`userId`/per-IP rate limit (e.g. `slowapi` or Container Apps-level throttling).
- **Effort to fix**: Days (1–2)
- **Blocks production?**: CONDITIONAL (blocking once real cost/traffic exposure exists; not
  blocking for continued DEV/academic use)

### RISK-004
- **Category**: Security
- **Title**: No security response headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options)
- **Description**: No middleware sets standard hardening headers on API responses.
- **Evidence**: Grepped `apps/api/src/` for each header name — zero hits.
- **Severity**: MEDIUM | **Likelihood**: MEDIUM | **Risk Score**: 3
- **Recommendation**: Add a small headers middleware (e.g. `secure` package or a hand-rolled
  `BaseHTTPMiddleware`).
- **Effort to fix**: Hours
- **Blocks production?**: CONDITIONAL

### RISK-005
- **Category**: Code Quality
- **Title**: No automated test-coverage measurement or CI gate
- **Description**: CLAUDE.md §11 states a 70% coverage target, but no `pytest-cov`/`coverage.py`
  tooling exists to measure or enforce it — the target is aspirational, not verified.
- **Evidence**: No coverage dependency in `pyproject.toml` or `apps/api/pyproject.toml`; no
  coverage step in `azure-pipelines.yml`'s `BackendQuality` stage.
- **Severity**: MEDIUM | **Likelihood**: MEDIUM | **Risk Score**: 3
- **Recommendation**: Add `pytest-cov`, publish a coverage report artifact, optionally gate on a
  minimum threshold.
- **Effort to fix**: Hours
- **Blocks production?**: NO

### RISK-006
- **Category**: Operational / Security
- **Title**: Web container's production command (`npm run preview`) is not a production server
- **Description**: Vite's own documentation states `vite preview` is not intended for production
  use (no production-grade static-file serving, caching, or compression semantics).
- **Evidence**: `apps/web/Dockerfile` — `CMD ["npm", "run", "preview", ...]`.
- **Severity**: MEDIUM | **Likelihood**: MEDIUM | **Risk Score**: 3
- **Recommendation**: Multi-stage build serving the static `dist/` output via `nginx`/`caddy`/
  similar.
- **Effort to fix**: Hours (4–8)
- **Blocks production?**: CONDITIONAL

### RISK-007
- **Category**: Code Quality / Security
- **Title**: No Python dependency lockfile
- **Description**: Both `pyproject.toml` files use `>=x,<y` version ranges with no lockfile —
  the exact resolved dependency set is not reproducible build-to-build.
- **Evidence**: `pyproject.toml`, `apps/api/pyproject.toml` (range-pinned only); no
  `poetry.lock`/`uv.lock`/equivalent found at repo root.
- **Severity**: MEDIUM | **Likelihood**: MEDIUM | **Risk Score**: 3
- **Recommendation**: Adopt `uv` or `pip-compile` to generate and commit a lockfile.
- **Effort to fix**: Hours
- **Blocks production?**: NO

### RISK-008
- **Category**: Architecture
- **Title**: Per-process singleton wiring limits horizontal scaling
- **Description**: `@lru_cache`-based dependency wiring and in-memory `CircuitBreaker` state do
  not share across replicas; the app is currently pinned to `maxReplicas: 1`. **Sharpened by
  `review/06_enterprise_architecture_assessment.md` (PBI-10-07, NEW-002)**: it is not only that
  `maxReplicas=1` today — `ops/bicep/modules/container-app.bicep`'s `scale:` block has no `rules`
  array at all (no HTTP-concurrency/CPU scale trigger), so raising `maxReplicas` alone would not
  cause the platform to actually scale under load; a scale rule would need to be added first, in
  addition to resolving the state-sharing question below.
- **Evidence**: `apps/api/src/api/dependencies.py` (12 `@lru_cache` sites); `az containerapp show`
  confirms `scale.maxReplicas: 1` live in DEV; `ops/bicep/modules/container-app.bicep`'s `scale:`
  block confirmed to contain only `minReplicas`/`maxReplicas`, no `rules:` key (PBI-10-07).
- **Severity**: MEDIUM | **Likelihood**: LOW | **Risk Score**: 2
- **Recommendation**: Not urgent at current scale; document the limitation in an ADR before ever
  raising `maxReplicas` above 1, add an explicit scale rule, and move circuit-breaker/cache state
  to a shared store first.
- **Effort to fix**: Days (design work, not urgent)
- **Blocks production?**: NO (conditional only on a future scale-out decision)

### RISK-009
- **Category**: Security
- **Title**: Both container images run as root
- **Description**: Neither `apps/api/Dockerfile` nor `apps/web/Dockerfile` declares a `USER`
  directive.
- **Evidence**: Direct read of both Dockerfiles — no `USER` line in either.
- **Severity**: MEDIUM | **Likelihood**: LOW | **Risk Score**: 2
- **Recommendation**: Add a non-root `USER` in both images.
- **Effort to fix**: Hours
- **Blocks production?**: CONDITIONAL

### RISK-010
- **Category**: Security
- **Title**: Network-layer isolation deferred in DEV (`enablePrivateNetworking=false`)
- **Description**: Cosmos DB, Key Vault, AI Search, and Azure OpenAI all have
  `publicNetworkAccess: Enabled` in the live DEV environment — mitigated by RBAC/Managed-Identity-
  only auth, but not network-isolated.
- **Evidence**: `ops/bicep/parameters/dev.bicepparam` (`enablePrivateNetworking = false`);
  `ops/bicep/main.bicep` (`enablePublicNetworkAccess: !enablePrivateNetworking`).
- **Severity**: MEDIUM | **Likelihood**: LOW | **Risk Score**: 2
- **Recommendation**: Already has a written production path — execute
  `docs/Architecture/adr/0002-vnet-private-endpoints-hardening.md` before any production
  deployment.
- **Effort to fix**: Days
- **Blocks production?**: CONDITIONAL (already ADR-planned, not blocking for DEV)

### RISK-011
- **Category**: Security / Operational
- **Title**: No security-event alerting (only infra-health metric alerts exist)
- **Description**: The 3 live metric alerts cover error rate/latency/availability, not
  security-relevant signals. This is now directly actionable: Microsoft Entra ID authentication
  is implemented (RISK-025, resolved) and every validation failure maps to a generic `401`
  (`get_current_user`) — a real, meaningful signal now exists (e.g. a burst of `401`s might
  indicate credential-stuffing or token tampering) that did not before authentication existed.
- **Evidence**: `ops/bicep/modules/monitor-alerts.bicep`; `az resource list` confirms only
  `alert-tmxap-dev-error-rate`/`-high-latency`/`-availability` exist; `apps/api/src/api/auth/dependency.py`'s
  `get_current_user` maps every validation failure to `401` with no dedicated log/metric today.
- **Severity**: MEDIUM | **Likelihood**: LOW | **Risk Score**: 2
- **Recommendation**: Add an alert on an abnormal `401` rate on the now-authenticated endpoints —
  no longer blocked on authentication landing (it has), only on the alert rule itself being
  written.
- **Effort to fix**: Hours
- **Blocks production?**: NO

### RISK-012
- **Category**: Code Quality
- **Title**: No pre-commit hooks
- **Description**: Lint/type errors are only caught at CI time, not before a local commit.
- **Evidence**: No `.pre-commit-config.yaml` at repo root.
- **Severity**: LOW | **Likelihood**: LOW | **Risk Score**: 1
- **Recommendation**: Add a `pre-commit` config running `ruff`/`eslint` on staged files.
- **Effort to fix**: Hours
- **Blocks production?**: NO

### RISK-013
- **Category**: Code Quality
- **Title**: `ruff` uses only its default rule set
- **Description**: No explicit `[tool.ruff.lint] select=[...]` — misses complexity checks
  (`C901`) and several stricter families the codebase's actual quality would likely already pass.
- **Evidence**: `pyproject.toml`'s `[tool.ruff]` block — only `line-length`/`target-version` set.
- **Severity**: LOW | **Likelihood**: LOW | **Risk Score**: 1
- **Recommendation**: Extend `select` to include `C90`, `UP`, `B`, `SIM` at minimum.
- **Effort to fix**: Hours
- **Blocks production?**: NO

### RISK-014
- **Category**: Code Quality
- **Title**: No frontend global error boundary
- **Description**: No React error boundary found in `apps/web/src/` — an unexpected render error
  would surface as a blank/broken UI rather than a graceful fallback.
- **Evidence**: Scan of `apps/web/src/` for `componentDidCatch`/`ErrorBoundary` — no match.
- **Severity**: LOW | **Likelihood**: LOW | **Risk Score**: 1
- **Recommendation**: Add a top-level error boundary component.
- **Effort to fix**: Hours
- **Blocks production?**: NO

### RISK-015
- **Category**: Code Quality
- **Title**: Dev dependencies present in the single-stage web runtime image
- **Description**: `apps/web/Dockerfile` is single-stage; `node_modules` (including
  devDependencies, needed only for the `npm run build` step) persists into the runtime image.
- **Evidence**: `apps/web/Dockerfile` — one `FROM` stage, `RUN npm ci` then `RUN npm run build`
  then `CMD npm run preview`, no multi-stage `COPY --from=`.
- **Severity**: LOW | **Likelihood**: LOW | **Risk Score**: 1
- **Recommendation**: Resolved as a side effect of fixing RISK-006 (multi-stage build).
- **Effort to fix**: Included in RISK-006
- **Blocks production?**: NO

### RISK-016
- **Category**: Architecture
- **Title**: No Cosmos DB schema/data migration strategy defined
- **Description**: No documented approach for evolving the conversation-history document shape.
- **Evidence**: No migration-related module or ADR found under `docs/Architecture/` or
  `src/services/conversation_store/`.
- **Severity**: LOW | **Likelihood**: LOW | **Risk Score**: 1
- **Recommendation**: Short ADR before the first breaking schema change.
- **Effort to fix**: Hours
- **Blocks production?**: NO

### RISK-017
- **Category**: Architecture
- **Title**: OpenTelemetry SDK not present (partial observability stack drift vs. CLAUDE.md §5)
- **Description**: App Insights + structured logging + correlation IDs exist and work; the
  specific OpenTelemetry SDK CLAUDE.md §5 names is not wired in.
- **Evidence**: No `opentelemetry-*` package in either `pyproject.toml`.
- **Severity**: LOW | **Likelihood**: LOW | **Risk Score**: 1
- **Recommendation**: Either adopt OpenTelemetry or update CLAUDE.md §5 to reflect the
  App-Insights-native approach actually in use.
- **Effort to fix**: Days (if adopting) / Hours (if just documenting)
- **Blocks production?**: NO

### RISK-018
- **Category**: Architecture
- **Title**: Azure Blob Storage (CLAUDE.md §5) not implemented for document storage
- **Description**: Knowledge documents are versioned as Markdown under `configs/knowledge_base/`
  instead.
- **Evidence**: No `src/services/*blob*` module; no storage-account Bicep module wired for
  document content (the one that exists, `storage-account.bicep`, backs the serverless Tool
  layer, not document storage).
- **Severity**: LOW | **Likelihood**: LOW | **Risk Score**: 1
- **Recommendation**: Either implement Blob Storage-backed knowledge ingestion or update
  CLAUDE.md §5/§4.4 to reflect the Markdown-in-repo approach actually in use.
- **Effort to fix**: Days (if implementing) / Hours (if documenting)
- **Blocks production?**: NO

### RISK-019
- **Category**: Architecture
- **Title**: Azure Functions/Durable Functions not the default runtime path
- **Description**: Deterministic Tools and Claims workflow both run in-process by default;
  Azure Functions code exists but is gated off (`deployServerlessToolLayer=false`). This is a
  deliberate, ADR-documented choice, not silent drift.
- **Evidence**: `TOOL_PROVIDER=inprocess`/`CLAIMS_WORKFLOW_PROVIDER=inprocess` confirmed live;
  `ops/functions/claims_tools/` exists but is not deployed;
  `docs/Architecture/adr/0003-azure-functions-tool-and-workflow-layer.md` documents the decision.
- **Severity**: LOW | **Likelihood**: LOW | **Risk Score**: 1
- **Recommendation**: None required — the architectural deviation is explained and
  feature-flagged, not silent.
- **Effort to fix**: N/A
- **Blocks production?**: NO

### RISK-020
- **Category**: Code Quality / Architecture
- **Title**: Per-Agent bespoke memory-prefill gating logic (forward-looking maintainability note)
- **Description**: Each of the three domain Agents independently re-derives which memory fields
  are safe to re-apply every turn vs. only on first entry — correct and well-justified per-Agent
  today, but a repeated-reasoning pattern that should be generalized if a fourth Agent is added.
- **Evidence**: `claims_agent.py`/`broker_agent.py`/`commercial_intake_agent.py`'s respective
  `_prefill_from_memory` functions; rationale documented in `docs/sprint_09/decisions.md` D-07.
- **Severity**: LOW | **Likelihood**: LOW | **Risk Score**: 1
- **Recommendation**: No action needed now; extract a shared helper if/when a fourth domain Agent
  is added.
- **Effort to fix**: N/A (deferred by design)
- **Blocks production?**: NO

### RISK-021
- **Category**: Operational
- **Title**: External-call timeouts not independently verified as tuned
- **Description**: Retry/circuit-breaker logic exists, but this review did not independently
  confirm each Azure SDK client call has an explicitly-tuned timeout distinct from the SDK's own
  default.
- **Evidence**: `src/core/resilience/` (retry/circuit-breaker present). **Updated by
  `review/06_enterprise_architecture_assessment.md` (PBI-10-07)**: the audit has now been
  performed — `AzureOpenAIProvider`, `AzureAISearchProvider`, and `CosmosConversationRepository`
  each construct their Azure SDK client with no explicit `timeout=`, relying entirely on the
  SDK's own default. By contrast, `OllamaLLMProvider`, `DurableWorkflowProvider`, and
  `AzureFunctionToolProvider` in the same codebase all pass an explicit
  `aiohttp.ClientSession(timeout=...)`. The finding is now confirmed, not merely suspected —
  severity unchanged, evidentiary status upgraded.
- **Severity**: LOW | **Likelihood**: LOW | **Risk Score**: 1
- **Recommendation**: Add an explicit `timeout=` to the three named client constructors, matching
  the pattern already used by the other three providers in this codebase.
- **Effort to fix**: Hours
- **Blocks production?**: NO

### RISK-027
- **Category**: Architecture / AI Governance
- **Title**: No confidence-threshold-based human escalation exists
- **Description**: CLAUDE.md §3 ("Human-in-the-Loop — sensitive, ambiguous, low-confidence,
  legal, financial, or coverage-related decisions must escalate to a person") and §4.1 (the
  Supervisor Agent "escalates below the confidence threshold") name a mechanism that does not
  exist in the code. `Intent.confidence` is only ever the literal constant `1.0` (keyword match)
  or `0.0` (no match) — never a graded score — and no threshold comparison or escalation branch
  exists anywhere in `src/supervisor/` or `src/agents/`. Identified in
  `review/06_enterprise_architecture_assessment.md` (PBI-10-07, NEW-001).
- **Evidence**: `src/supervisor/intent.py:59,62,65,67` (constants `1.0`/`0.0`);
  `src/supervisor/models.py:31` (`confidence: float = 1.0` default); grep of
  `confidence|escalat` across `src/supervisor/**`/`src/agents/**` (case-insensitive) — no
  escalation branch found; grep of `ESCALATED` across every `.py` file in the repository —
  `src/domain/conversation.py:39`'s `ConversationStatus.ESCALATED` definition is the *only* match,
  confirming the enum value is never set anywhere.
- **Severity**: MEDIUM | **Likelihood**: HIGH (structurally absent for every conversation, not an
  edge case) | **Risk Score**: 5
- **Recommendation**: Implement a real confidence signal and wire it to
  `ConversationStatus.ESCALATED`, or correct CLAUDE.md §3/§4.1 to describe current
  keyword-routing-only behavior accurately. Either closes the gap between documented and actual
  architecture.
- **Effort to fix**: Days (if implementing) / Hours (if correcting the documentation instead)
- **Blocks production?**: CONDITIONAL — not a security vulnerability, but a real gap against this
  platform's own stated governance principle in a domain (insurance) where ambiguous/
  low-confidence/coverage-related cases are not hypothetical.

### RISK-028
- **Category**: Architecture / Operational
- **Title**: No autoscale rule configured on either Container App
- **Description**: See RISK-008 above, which this finding extends with the specific,
  independently-verified fact that `container-app.bicep`'s `scale:` block defines no `rules`
  array at all — not merely that `maxReplicas=1` today. Tracked as its own entry per
  `review/06_enterprise_architecture_assessment.md` (PBI-10-07, NEW-002) since it is a distinct,
  independently actionable fact from RISK-008's state-sharing concern.
- **Evidence**: `ops/bicep/modules/container-app.bicep` — `scale: { minReplicas: minReplicas,
  maxReplicas: maxReplicas }`, no `rules:` key present (confirmed via direct read, PBI-10-07).
- **Severity**: MEDIUM | **Likelihood**: LOW | **Risk Score**: 3
- **Recommendation**: Add an explicit HTTP-concurrency (or CPU-based) scale rule before ever
  raising `maxReplicas` above 1 — in addition to, not instead of, RISK-008's state-sharing fix.
- **Effort to fix**: Hours (once the state-sharing design question in RISK-008 is resolved)
- **Blocks production?**: NO (current single-replica DEV/academic scope does not require this)

### RISK-029
- **Category**: Code Quality
- **Title**: Resilience threshold constants duplicated across three provider files
- **Description**: `_CIRCUIT_BREAKER_FAILURE_THRESHOLD`, `_CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS`,
  `_RETRY_MAX_ATTEMPTS` are declared independently and identically in
  `azure_openai_provider.py`, `cosmos.py`, and `azure_ai_search_provider.py` rather than as a
  single shared constant. Identified in `review/06_enterprise_architecture_assessment.md`
  (PBI-10-07, NEW-003).
- **Evidence**: Same constant names/values confirmed declared locally in each of the three files.
- **Severity**: LOW | **Likelihood**: LOW | **Risk Score**: 1
- **Recommendation**: Extract to a shared resilience-defaults module if/when a fourth
  resilience-wrapped provider is added — not urgent today with only three consumers, consistent
  with CLAUDE.md §7's "no premature abstraction" preference.
- **Effort to fix**: Hours
- **Blocks production?**: NO

---

## Resolved findings

Carried in this register for audit-trail purposes — each was investigated against current `main`
(HEAD `a02ba19`) with direct evidence, not assumed.

### RISK-022 — RESOLVED
- **Category**: Architecture / Operational
- **Title**: Retry-with-backoff and circuit breaker did not exist around external calls
- **Description**: Azure OpenAI, Cosmos DB, and Azure AI Search calls had no resilience wrapper —
  a single transient failure on any of them failed the whole request.
- **Evidence of resolution**: `src/core/resilience/{retry.py,circuit_breaker.py}` exist and are
  imported and wired into all three external-call providers
  (`src/llm/azure_openai_provider.py`, `src/rag/azure_ai_search_provider.py`,
  `src/services/conversation_store/cosmos.py`); 11 dedicated unit tests
  (`tests/unit/core/resilience/test_circuit_breaker.py` ×6, `test_retry.py` ×5), confirmed
  passing. Delivered under PBI-08-01 (`docs/sprint_08/README.md`, Finding A-07).
- **Severity/Likelihood at time of finding**: MEDIUM/HIGH | **Status**: Fully resolved, no
  caveat.

### RISK-023 — RESOLVED
- **Category**: Code Quality
- **Title**: No automated conversational or end-to-end regression tests existed
- **Description**: `tests/e2e/` and `tests/conversational/` contained only placeholder
  (`.gitkeep`) files — real-system, multi-turn, and load behavior had no automated regression
  protection; only mocked unit tests existed.
- **Evidence of resolution**: 4 real test files now exist across both directories — 20 test
  cases total (`tests/e2e/test_load.py` ×2 concurrency/load tests;
  `tests/conversational/test_prompt_injection_and_security_scenarios.py` ×7;
  `test_global_memory_and_multi_domain_orchestration.py` ×6;
  `test_final_validation_defect_regressions.py` ×5) — confirmed passing (`pytest -q` on both
  directories: 20 passed). Test bodies assert specific business/security outcomes (e.g.
  injection-shaped payloads, cross-domain memory reuse), not placeholder smoke checks. Delivered
  under PBI-08-01 (Finding A-17) and PBI-09-01.
- **Severity/Likelihood at time of finding**: MEDIUM/HIGH | **Status**: Fully resolved, no
  caveat.

### RISK-024 — PARTIALLY RESOLVED
- **Category**: Operational
- **Title**: CLAUDE.md §14's Sprint 05 "Hardening and final evidence" scope had not been executed
- **Description**: The original sprint sequence named prompt-injection/adversarial testing,
  dashboards, cost telemetry, load/resilience testing, and final architecture review as Sprint
  05 deliverables; none had been executed under any sprint number.
- **Evidence of resolution**: prompt-injection/adversarial testing (7 tests, see RISK-023),
  load/resilience testing (2 tests, see RISK-023 and RISK-022), CI dependency/secret scanning
  (`azure-pipelines.yml`'s `SecurityScan` stage), and a hardening validation document
  (`docs/sprint_08/validation.md`) all now exist and pass — delivered under PBI-08-01/Sprint 08
  rather than as a literally-numbered "Sprint 05," but the substance of the mandate is met.
- **What remains open**: the original mandate also named **dashboards** and **cost telemetry**.
  What exists today is 3 Azure Monitor *metric alerts* (`monitor-alerts.bicep`) — not a curated
  visual dashboard/workbook — and a *documented cost-telemetry measurement methodology*
  (`docs/sprint_08/evidence/latency-and-cost-telemetry.md`) rather than a live, automated
  cost-tracking pipeline. This residual gap is LOW severity/LOW likelihood, does not block
  production or continued DEV use, and is small enough not to warrant its own numbered open
  `RISK-ID` — tracked here as the unresolved remainder of this finding.
- **Severity/Likelihood at time of finding**: MEDIUM/MEDIUM | **Status**: Substance resolved;
  "dashboards" and automated cost telemetry remain open (LOW/LOW, informational).

### RISK-025 — RESOLVED
- **Category**: Security
- **Title**: No authentication existed on any API endpoint
- **Description**: `POST /chat`, `GET /conversations`, `GET /conversations/{id}` trusted an
  unauthenticated, client-supplied `userId` — any caller could act as, or read the history of,
  any other `userId` they could guess or observe. Formerly RISK-001 in this register.
- **Evidence of resolution**: Microsoft Entra ID authentication is implemented and live in DEV
  (PBI-11-01 through PBI-11-01D). `apps/api/src/api/auth/` (`EntraTokenValidator`, `JwksProvider`,
  `get_current_user`) validates signature (RS256 via live JWKS), expiry, audience (exact-match
  against the bare API client ID GUID — corrected from an initial Application ID URI
  misconfiguration, PBI-11-01D), and issuer (tenant-self-consistency check, correct for the
  `/common` multi-tenant authority) on every call to all three business routes, confirmed by
  direct read of `apps/api/src/api/routes/chat.py` and `conversations.py`
  (`Depends(get_current_user)` on each). `ChatRequest.user_id`/the `userId` query parameter are
  now optional, deprecated, and never read for authorization — identity is derived exclusively
  from the validated token as `f"{tid}:{oid}"`. 24 dedicated tests
  (`tests/unit/api/test_auth.py`) cover signature/expiry/audience/issuer rejection paths and pass.
  Frontend (`apps/web/src/auth/`) uses OAuth2 Authorization Code + PKCE via MSAL Browser/React —
  no client secret introduced anywhere (grepped, none found). Full record:
  [ADR-0010](../docs/Architecture/adr/0010-enterprise-authentication-entra-id.md).
- **Severity/Likelihood at time of finding**: HIGH/HIGH (Risk Score 8) | **Status**: Fully
  resolved for the authentication mechanism itself. Two genuinely new, narrower gaps surfaced
  while doing this work and are tracked separately, not folded back into this finding: no rate
  limiting exists for authenticated callers (RISK-003, pre-existing, now confirmed to still apply
  post-auth) and no security-event alert distinguishes a burst of `401`s from routine errors
  (extends RISK-011).

### RISK-026 — RESOLVED
- **Category**: Security
- **Title**: IDOR — any caller could read another user's full conversation history
- **Description**: Direct consequence of RISK-025/RISK-001's missing identity binding —
  `GET /conversations/{id}?userId=X` returned conversation content for whichever `userId` was
  supplied, with no ownership check. Formerly RISK-002 in this register.
- **Evidence of resolution**: Resolved as a direct consequence of RISK-025's fix — identity is
  now server-derived from the validated token, never from a client-supplied value, so there is no
  longer a caller-controlled key to substitute. Proven, not just designed: three dedicated
  regression tests in `tests/unit/api/test_auth.py`
  (`test_user_b_cannot_read_user_as_conversation_even_supplying_user_as_old_userid`,
  `test_user_b_conversation_list_never_includes_user_as_conversations`,
  `test_two_different_authenticated_identities_get_independent_conversation_histories`) mint two
  genuinely different Entra identities and confirm neither can read, list, or infer the other's
  conversation data (`404`, not `200`, even when the attacker supplies the victim's real old
  `userId` and real `conversationId`) — all passing.
- **Severity/Likelihood at time of finding**: HIGH/HIGH (Risk Score 8) | **Status**: Fully
  resolved, no caveat — this finding had no independent fix separate from RISK-025's, and both
  are now closed together.

---

## Risk Score Summary

Updated after re-running this review against the current repository (PBI-10-06), then again after
the 10-dimension enterprise architecture reassessment (PBI-10-07, `06_enterprise_architecture_
assessment.md`). RISK-001/RISK-002 (score 8 each, the two highest-scored open findings in the
original version of this register) are resolved — see RISK-025/RISK-026. Three new findings
(RISK-027/028/029) were added by PBI-10-07's independent reassessment.

| Score | Count | Risk IDs |
|---|---|---|
| 5 | 1 | RISK-027 |
| 3 | 6 | RISK-003, RISK-004, RISK-005, RISK-006, RISK-007, RISK-028 |
| 2 | 4 | RISK-008, RISK-009, RISK-010, RISK-011 |
| 1 | 11 | RISK-012 – RISK-021, RISK-029 |
| **Total open** | **22** | |
| — | 5 | RISK-022 (resolved), RISK-023 (resolved), RISK-024 (partially resolved), RISK-025 (resolved), RISK-026 (resolved) |

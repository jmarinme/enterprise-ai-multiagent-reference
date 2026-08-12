# 06 — Final Enterprise Architecture Assessment (PBI-10-07)

**Date**: 2026-08-11 | **Scope**: full reassessment of the current repository across 10
dimensions, performed without reusing any prior review's conclusions — every claim below is
backed by a direct file:line citation or a command actually run in this session. Where this
assessment's finding differs from `01_architecture_review.md`/`02_security_review.md`
(2026-08-11, PBI-10-06), that document is treated as superseded on the specific point, not as a
starting assumption.

Severity legend (matches `04_risk_register.md`): **CRITICAL** / **HIGH** / **MEDIUM** / **LOW** /
**INFO**. Score legend: CRITICAL×HIGH=10, HIGH×HIGH=8, HIGH×MEDIUM=6, MEDIUM×HIGH=5,
MEDIUM×MEDIUM=3, LOW×any=1–2.

---

## 1. Architecture — 4/5

- Layered Supervisor → domain Agent → Tool design is real and consistently enforced: each of the
  three domain-agent verticals (`src/agents/claims/`, `broker/`, `commercial/`) imports only from
  its own subpackage — zero cross-vertical imports found (grepped `from src.agents.(broker|
  commercial|claims)` across all three).
- 15 `Protocol`-based abstractions exist and are genuinely used as extension seams (`LLMProvider`,
  `ConversationRepository`, `KnowledgeProvider`, `ToolProvider`, `ClaimsWorkflowProvider`,
  `IntentResolver`, `Agent`/`AgentRegistry`, etc.) — this is the mechanism every provider swap in
  this platform (mock↔Azure OpenAI, in-memory↔Cosmos, in-process↔Azure Functions,
  Entra-token-validated↔none) has been implemented through, without touching call sites.
- **Held back by**: per-process singleton state (`@lru_cache` on every provider factory in
  `apps/api/src/api/dependencies.py`; in-memory `CircuitBreaker` state, explicitly self-documented
  as "not distributed/shared across Container App replicas" in `src/core/resilience/
  circuit_breaker.py`'s own header) — architecturally sound for a single-replica deployment, a
  real constraint the moment horizontal scaling is needed (see §4 Scalability).
- **Asymmetry worth naming**: `ClaimsAgent` (`src/agents/claims_agent.py:169`) is wired with RAG,
  a `Grounder`, and a `ToolCallingOrchestrator`; `BrokerAgent`/`CommercialIntakeAgent`
  (`broker_agent.py:85`, `commercial_intake_agent.py:75`) use a plain `ToolExecutor` with none of
  that. All three satisfy the same `Agent` Protocol structurally, but the capability gap between
  them is real, not just deferred scope — consistent with the fact that Claims was the first and
  only fully-migrated vertical (ADR-0003/Sprint 06), not a defect.

## 2. Security — 4/5 (up from 2/5, PBI-10-06)

Re-verified, not carried forward: `apps/api/src/api/auth/` (`EntraTokenValidator`, `JwksProvider`,
`get_current_user`) validates signature/expiry/audience/issuer on every request to `POST /chat`,
`GET /conversations`, `GET /conversations/{id}`; identity is `f"{tid}:{oid}"`, never
client-supplied. `tests/unit/api/test_auth.py` — 24 tests re-confirmed present via direct file
read, including the three IDOR regression tests. See §11 below for the point-by-point check
against the five specifically-named prior findings.

- **Still open, unchanged by the authentication work**: no rate limiting on any endpoint
  (authenticated or not — `ChatRequest.message` has no `max_length`, grepped, none found); no
  security response headers (`CSP`/`HSTS`/`X-Frame-Options` — grepped `apps/api/src/`, zero
  hits); both Dockerfiles run as root (no `USER` directive in either); network isolation deferred
  in DEV (`enablePrivateNetworking=false`); no alert distinguishes a burst of `401`s from routine
  errors (confirmed: grepped `401`/`unauthorized` across `ops/bicep`, zero hits — only the three
  infra-health alerts exist).

## 3. Enterprise readiness — 3/5 (new dimension, not separately scored before)

- **Identity/access**: RBAC-only Azure resource access (Cosmos `disableLocalAuth: true`, Key
  Vault RBAC-only, ACR `adminUserEnabled: false`), single Managed Identity for service-to-service,
  now paired with real end-user Entra ID authentication — a coherent, enterprise-appropriate
  identity story end to end.
- **Audit/compliance**: correlation-ID-joined structured JSON logs exist, but there is no
  long-term audit-log retention policy or SIEM/export target beyond Log Analytics' own default
  retention (`logAnalyticsRetentionInDays=30` in DEV) — adequate for an academic DEV environment,
  not evidenced as meeting any named compliance retention requirement.
- **Disaster recovery**: Cosmos DB periodic backup is enabled (`backupIntervalInMinutes: 240`,
  `backupRetentionIntervalInHours: 8`), but `docs/Architecture/Administrator_Guide.md` §8.2 itself
  states "no runbook, script, or sprint record ... documents having ever performed (or tested) a
  restore-from-backup operation" and "no cross-region disaster recovery." This is a genuine gap
  for any enterprise-readiness claim beyond academic/DEV scope.
- **Cost governance**: a documented cost-telemetry *methodology* exists
  (`docs/sprint_08/evidence/latency-and-cost-telemetry.md`, per `04_risk_register.md` RISK-024)
  but no automated cost-tracking pipeline or budget alert exists.
- **SLA/support model**: none defined anywhere in the repository — appropriate for the academic
  scope this platform explicitly claims (CLAUDE.md §1), but a real gap if "enterprise readiness"
  is read as "ready for a real enterprise SLA commitment" rather than "built with enterprise
  patterns."

## 4. Scalability — 2/5 (new dimension; the lowest score in this assessment)

- **Fixed at exactly 1 replica, not just capped there**: `ops/bicep/parameters/dev.bicepparam` —
  `apiMinReplicas = 1`, `apiMaxReplicas = 1`, `webMinReplicas = 1`, `webMaxReplicas = 1`.
- **New finding, independently verified in this assessment**: `ops/bicep/modules/
  container-app.bicep`'s `scale:` block (lines ~120-123) contains only `minReplicas`/`maxReplicas`
  — **no `rules` array (HTTP concurrency or CPU-based scale rule) is defined at all.** This means
  raising `maxReplicas` alone would not make the platform scale under load — Container Apps has
  no trigger telling it *when* to add a replica. This is a materially different (and more
  actionable) finding than "replicas are capped at 1," and was not previously called out this
  specifically in `04_risk_register.md` RISK-008. See §12, new finding NEW-002.
- **What would need to change before scale-out is safe**: the per-process `CircuitBreaker` state
  and `@lru_cache` singletons (§1) would need to move to shared state (Redis or similar) or be
  proven safe to duplicate per-replica — neither has been evaluated, per `CLAUDE.md`'s own
  explicit deferral of Redis pending an ADR.
- **What already scales cleanly**: Cosmos DB is Serverless (scales RU/s automatically, no fixed
  throughput ceiling in DEV); both the Cosmos and Azure OpenAI clients use the async SDK with a
  single reused client instance (no per-request connection churn); the API itself is stateless
  HTTP (no server-side session/sticky-routing requirement).

## 5. Reliability — 4/5

- Retry (`src/core/resilience/retry.py`): 3 attempts, exponential backoff (`0.5s * 2^(n-1)`,
  capped 8s) with full jitter. Circuit breaker (`circuit_breaker.py`): opens after 5 consecutive
  failures, 30s reset-to-half-open, a half-open trial failure reopens immediately. Both are wired
  into exactly the three external-call providers that need them: `AzureOpenAIProvider`,
  `CosmosConversationRepository`, `AzureAISearchProvider` — confirmed by direct import grep, not
  assumed.
- `GET /ready` runs all three dependency checks concurrently, each under a 5-second
  `asyncio.timeout`, correctly short-circuiting checks for unconfigured providers to `"ok"`
  rather than false-failing.
- **New finding, independently verified in this assessment**: none of `AzureOpenAIProvider`,
  `AzureAISearchProvider`, or `CosmosConversationRepository` passes an explicit `timeout=` to its
  underlying Azure SDK client constructor — each relies entirely on the SDK's own built-in
  default. This is in direct contrast to three *other* providers in the same codebase
  (`src/llm/ollama_provider.py`, `src/core/workflow_provider/durable.py`,
  `src/core/tool_provider/azure_function.py`), which all pass an explicit `aiohttp.ClientSession
  (timeout=...)`. This sharpens `04_risk_register.md` RISK-021 ("not independently verified") into
  a confirmed, specific gap — see §12.
- **Idempotency**: only one Tool (`AdjusterAssignmentTool`) documents and implements idempotency
  explicitly (assignment is a pure function of the claim reference). No idempotency-key mechanism
  exists for claim creation itself — a retried `create_claim_notice` call after a transient
  failure has not been proven not to double-register a claim. Not independently exploited in this
  assessment (no reproduction attempted), reported as an unverified gap.

## 6. Maintainability — 4/5

- Only 2 files across `src/` and `apps/api/src/` exceed 500 lines (`claims/workflow.py` at 739,
  `broker/workflow.py` at 545) — a genuinely small-file codebase for its size.
- `mypy` enables `disallow_untyped_defs`/`warn_unused_ignores`/`no_implicit_optional` but is not
  full `strict = true` (no `disallow_untyped_calls`/`disallow_any_generics`). `ruff` uses only its
  default rule set (no explicit `select=` extending to `C90`/`UP`/`B`/`SIM`) — both previously
  tracked (RISK-013), re-confirmed here with the specific missing mypy flags named for the first
  time.
- **New finding, minor**: the retry/circuit-breaker threshold constants
  (`_CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5`, `_CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS = 30.0`,
  `_RETRY_MAX_ATTEMPTS = 3`) are declared independently in each of the three consuming files
  rather than as shared, single-source-of-truth constants — a small DRY gap; a future change to
  the platform's standard resilience posture requires editing three files identically rather than
  one. See §12, new finding NEW-003 (LOW).

## 7. DevOps — 3/5 (new dimension; folds in and extends prior CI/CD notes)

- The pipeline (`azure-pipelines.yml`) is comprehensive and correctly gated: Quality/Security
  stages run on every push and PR; `ContainerBuildAndPush`/`InfrastructureDeploy`/`DeployDev`/
  `SmokeTests` are all `condition: isDeployRun == true` (main-branch pushes only, confirmed via
  `Build.SourceBranch` check). Image tags always encode build ID + commit SHA — `"latest"` is
  never used anywhere in the file.
- Bicep is validated twice: an offline `az bicep build` on every run, plus a live `az deployment
  group validate` immediately before every real `az deployment group create`.
- **Held back**: `docs/Architecture/Deployment_Guide.md` §11.8 documents that this pipeline has
  never had a confirmed, real, automated end-to-end run — Azure DevOps Hosted Parallelism is
  reported unavailable for this organization, and every deployment evidenced throughout this
  repository's sprint history was performed via direct, manually-invoked `az`/`docker` commands,
  not by the pipeline executing. A well-authored pipeline that has not been exercised end-to-end
  is a materially different readiness state than one that has — this assessment scores DevOps on
  that basis, not on the YAML's design quality alone.
- No branch-protection/required-reviewer configuration is present in-repo (Azure DevOps branch
  policies are portal-side and not evidenced by any file here) — not a defect, just unverifiable
  from this codebase.

## 8. Observability — 3/5

- Correlation-ID propagation and structured JSON logging are real and consistently used
  end-to-end (`CorrelationIdMiddleware`, `CorrelationIdFilter`, `JsonFormatter`). Three metric
  alerts (error rate, latency, availability) are live, confirmed against real Application
  Insights/Container-App metric names.
- **Held back**: the alerting Action Group has zero email receivers by default (`alertEmailAddress`
  defaults to `''`) — alerts fire and are visible in the Azure Portal but page nobody until this
  is set. No dashboard/workbook exists (grepped `workbook`/`dashboard` across `ops/bicep`, zero
  hits) — only raw alert rules. No security-event alert exists (no rule keyed on `401` rate or
  any auth-failure signal). OpenTelemetry, named explicitly in CLAUDE.md §5's technology stack, is
  not present in any `pyproject.toml` in this repository — telemetry today is App Insights +
  hand-rolled structured logging, not the OTel SDK the architecture document names.

## 9. AI architecture — 5/5

- Clean separation of concerns, verified directly, not merely claimed: `LLMProvider` is a Protocol
  (`src/llm/provider.py`) with `AzureOpenAIProvider`/`MockLLMProvider`/`OllamaLLMProvider` as
  swappable implementations; `AzureOpenAIProvider` prefers Entra ID (`DefaultAzureCredential`)
  over an API key, and never reads a secret from `os.environ` directly (routed through
  `SecretProvider`).
- Prompts are externalized as Markdown under `configs/prompts/` (5 files: supervisor, claims,
  broker_services, commercial_intake, fallback) — not embedded as Python string literals.
- RAG has a genuine, typed grounding layer: `src/rag/grounder.py`'s `Grounder` deduplicates and
  deterministically orders retrieved chunks into a `GroundedContext` with numbered `Citation`
  references — this is what lets a chat response say "Basado en N fuente(s)" truthfully rather
  than as a cosmetic label.
- **Tool-calling is correctly deterministic, not LLM-trusted**: `ToolCallingOrchestrator`
  validates a requested tool name against the `ToolRegistry` (existence check) and against
  `context.allowed_tools` (authorization check) *before* ever calling `Tool.execute()` — the
  module's own docstring states "No eval(), no dynamic import, no shell/process execution
  anywhere in this module." This is architecture principle #3 (CLAUDE.md §3, "Tool Calling for
  business action") implemented exactly as specified, independently confirmed by reading the
  actual validation code path, not inferred from the principle's existence.
- **Update (PBI-12-04, after a dedicated gap analysis against the course's named primary pattern
  — ReAct + Tool Calling, PBI-12-01)**: `ToolCallingOrchestrator.run()` was independently
  confirmed to already implement a bounded Reason → Act → Observe → Reason loop (not a
  single-shot call) — previously wired only into `ClaimsAgent`. This has since been generalized
  to `BrokerAgent`/`CommercialIntakeAgent` with 18 new passing tests, hardened with
  duplicate-tool-call detection and an opt-in per-call timeout, and formally documented in
  [ADR-0011](../docs/Architecture/adr/0011-react-pattern-for-tool-orchestrated-reasoning.md).
  This does not change this section's 5/5 score (the underlying mechanism was already sound) —
  it closes the "only wired into one Agent, never named as ReAct" gap that score was implicitly
  carrying.
- Prompt-injection tests (`tests/conversational/test_prompt_injection_and_security_scenarios.py`)
  assert concrete, specific outcomes — no internal diagnostic leakage, no bypass of the
  deterministic claims flow via a fake-authority message, SQL/XSS-shaped input handled inertly,
  extremely long input does not hang, correlation ID cannot be spoofed via message content. This
  is the strongest-scoring dimension in this assessment because every claim about it is backed by
  a passing, specific, adversarial test — not just a design description.

## 10. Multi-agent orchestration — 3/5

- Intent resolution is rule-based (`RuleBasedIntentResolver`, keyword matching, no LLM/embeddings
  involved in routing) — a deliberate, correctly-motivated determinism choice (the class's own
  docstring: "validate the orchestration architecture end-to-end" without AI-routing
  non-determinism).
- Mid-conversation domain switching works correctly and is regression-tested: the orchestrator's
  "sticky" fallback (stay with the currently active agent when a follow-up message matches no new
  domain keyword) and `carry_forward_other_agent_state` (an agent's in-progress state survives a
  domain switch without leaking into another agent's behavior) are both real, verified mechanisms.
- **New finding, independently verified in this assessment, the most significant new finding in
  this entire pass**: CLAUDE.md §3 states "Human-in-the-Loop — sensitive, ambiguous, low-
  confidence, legal, financial, or coverage-related decisions must escalate to a person," and §4.1
  describes the Supervisor Agent as one that "escalates below the confidence threshold." **No such
  mechanism exists in the code.** `Intent.confidence` (`src/supervisor/models.py:31`, default
  `1.0`) is only ever set to the literal constant `1.0` (a keyword match) or `0.0` (no match) —
  there is no computed, graded confidence score and no threshold comparison anywhere in
  `src/supervisor/` or `src/agents/` (grepped `confidence`/`escalat` across both directories,
  case-insensitive — zero escalation branches found). `ConversationStatus.ESCALATED`
  (`src/domain/conversation.py:39`) is a defined enum value that **is never referenced or set
  anywhere else in the entire codebase** (grepped `ESCALATED` across every `.py` file — the one
  definition is the only match) — a placeholder for a Human-in-the-Loop feature that was named in
  the architecture but never wired to any code path. See §12, new finding NEW-001 (the highest-
  scored new finding in this assessment).
- **Update (PBI-12-04)**: unrelated to NEW-001 above — this is a different gap. Generalizing
  `ToolCallingOrchestrator` to all three specialist agents (see §9's update note) does not
  address confidence-based escalation; the two remain separate findings. This section's 3/5
  score is unchanged by PBI-12-04.

---

## 11. Point-by-point check on the five previously-named findings

| Finding | Status | Evidence |
|---|---|---|
| **Missing Authentication** | **RESOLVED** | `apps/api/src/api/auth/` validates every request to all three business routes; `get_current_user` is a required `Depends()` on each, confirmed by direct read of `chat.py`/`conversations.py`. |
| **Client-side Identity Trust** | **RESOLVED** | `ChatRequest.user_id`/`userId` query param are optional, deprecated, and never read by any route handler — `current_user.user_id` (from the validated token) is the only identity value ever passed to `ConversationRepository`, confirmed by direct read. |
| **IDOR** | **RESOLVED** | `tests/unit/api/test_auth.py`'s three dedicated regression tests (re-confirmed present in this assessment) mint two different Entra identities and prove neither can read, list, or infer the other's conversation data — including the specific original attack (supplying the victim's old `userId`), which now returns `404`. |
| **JWT Validation** | **RESOLVED** | `EntraTokenValidator` validates signature (RS256 via live JWKS), expiry, audience (bare GUID, corrected PBI-11-01D), and issuer (tenant-self-consistency for `/common`) — all four checks confirmed present by direct code read, each with a corresponding rejection test in `test_auth.py`. |
| **Enterprise Authentication** | **RESOLVED** | OAuth2 Authorization Code + PKCE via MSAL Browser/React, no client secret in the SPA (grepped, none found), multi-tenant `/common` authority supporting internal and external users — a genuine enterprise-identity pattern, not a bespoke/local auth scheme. |

None of the five re-opened under this fresh assessment. Every one was verified against current
code in this session, not assumed carried-forward.

---

## 12. New findings (not previously tracked in `04_risk_register.md`)

### NEW-001 — No confidence-threshold-based human escalation exists
- **Category**: Architecture / AI Governance
- **Description**: CLAUDE.md's own stated architecture principle (Human-in-the-Loop, §3) and the
  Supervisor Agent's own named responsibility ("escalates below the confidence threshold," §4.1)
  are not implemented. `Intent.confidence` is binary (1.0 keyword-match / 0.0 no-match), never a
  graded score; no threshold comparison or escalation branch exists in `src/supervisor/` or
  `src/agents/`; `ConversationStatus.ESCALATED` is defined but never set anywhere in the codebase.
- **Evidence**: `src/supervisor/intent.py:59,62,65,67`; `src/supervisor/models.py:31`; grep of
  `confidence|escalat` across `src/supervisor/**`/`src/agents/**` (case-insensitive) — no match
  beyond the constants above; grep of `ESCALATED` across every `.py` file in the repository — one
  match, its own definition.
- **Severity**: MEDIUM | **Likelihood**: HIGH (structurally absent for every conversation, not a
  rare edge case) | **Risk Score**: 5
- **Recommendation**: Either implement a real confidence signal (e.g., a graded intent-matching
  score, or an LLM-based ambiguity check gated by the existing "LLM is not the source of truth"
  principle so it only ever *recommends* escalation, never decides business outcomes) and wire it
  to `ConversationStatus.ESCALATED`, or update CLAUDE.md §3/§4.1 to accurately describe the
  current keyword-routing-only behavior rather than naming an unimplemented mechanism. Either
  outcome closes the gap between documented and actual architecture — leaving it undocumented is
  the one option that does not.
- **Effort to fix**: Days (design + implementation) if building it; Hours if instead correcting
  the architecture documentation to match current behavior.
- **Blocks production?**: CONDITIONAL — not a security vulnerability, but a real gap against this
  platform's own stated governance principle for an insurance domain where "ambiguous, low-
  confidence, coverage-related" cases are not hypothetical.

### NEW-002 — No autoscale rule configured on either Container App
- **Category**: Architecture / Operational
- **Description**: Extends `04_risk_register.md` RISK-008 with a more specific, independently
  verified fact: it is not just that `maxReplicas=1` in DEV — the `scale:` block in
  `container-app.bicep` has no `rules` array at all (no HTTP-concurrency or CPU-based trigger).
  Raising `maxReplicas` alone would not cause the platform to scale under load; a scale rule would
  need to be added first.
- **Evidence**: `ops/bicep/modules/container-app.bicep` — `scale: { minReplicas: minReplicas,
  maxReplicas: maxReplicas }`, no `rules:` key present (confirmed via direct grep of the file in
  this assessment).
- **Severity**: MEDIUM | **Likelihood**: LOW (not urgent at current single-replica/academic scale)
  | **Risk Score**: 3
- **Recommendation**: Treat as part of RISK-008's existing remediation — before ever raising
  `maxReplicas` above 1, add an explicit HTTP-concurrency scale rule *and* resolve the
  per-process `CircuitBreaker`/`@lru_cache` state-sharing question RISK-008 already names.
- **Effort to fix**: Hours (the Bicep change itself) once the state-sharing design question is
  resolved.
- **Blocks production?**: NO (current single-replica DEV/academic scope does not require this).

### NEW-003 — Resilience threshold constants duplicated across three provider files
- **Category**: Code Quality
- **Description**: `_CIRCUIT_BREAKER_FAILURE_THRESHOLD`, `_CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS`,
  `_RETRY_MAX_ATTEMPTS` are declared independently and identically in
  `azure_openai_provider.py`, `cosmos.py`, and `azure_ai_search_provider.py` rather than as a
  single shared constant/config object.
- **Evidence**: grep confirms the same three constant names/values declared locally in each of
  the three files.
- **Severity**: LOW | **Likelihood**: LOW | **Risk Score**: 1
- **Recommendation**: Extract to a shared `src/core/resilience/defaults.py` (or similar) if/when
  a fourth resilience-wrapped provider is added — consistent with this codebase's own documented
  "no premature abstraction" preference (CLAUDE.md §7), so not urgent today with only three
  consumers.
- **Effort to fix**: Hours
- **Blocks production?**: NO

### Sharpened (not new, but materially more specific than before): explicit SDK client timeouts
- `04_risk_register.md` RISK-021 previously read "not independently verified" — this assessment
  independently verified it: `AzureOpenAIProvider`, `AzureAISearchProvider`, and
  `CosmosConversationRepository` each construct their SDK client with no explicit `timeout=`,
  while three *other* providers in the same codebase (`OllamaLLMProvider`,
  `DurableWorkflowProvider`, `AzureFunctionToolProvider`) do pass one explicitly. RISK-021's
  severity/score are unchanged (still LOW/LOW/1) — the finding is now confirmed rather than
  merely suspected, which changes its evidentiary status, not its severity.

---

## 13. Comparison with the previous assessment (PBI-10-06, `01`–`05`, 2026-08-11)

| Dimension | Previous score | This assessment | Change |
|---|---|---|---|
| Architecture & Design | 4/5 | 4/5 (§1) | Unchanged — re-verified, same conclusion |
| Security Posture | 4/5 (up from 2/5 same day) | 4/5 (§2) | Unchanged from PBI-10-06's own update; re-verified independently in this pass |
| Enterprise readiness | *(not separately scored before)* | 3/5 (§3) | New dimension |
| Scalability | *(folded into Architecture/Operational before)* | 2/5 (§4) | New dimension — the lowest score in this assessment, and a real, specific, newly-verified gap (no scale rule, not just a replica cap) |
| Reliability | *(folded into Operational Readiness, 3/5, before)* | 4/5 (§5) | New dimension, scored higher than the old blended "Operational Readiness" because resilience mechanics specifically are strong; the weaker operational sub-items (rate limiting, root containers) are now scored under Security/Enterprise readiness instead |
| Maintainability | *(folded into Code Quality, 4/5, before)* | 4/5 (§6) | New dimension, consistent with the prior blended score |
| DevOps | *(folded into Operational Readiness before)* | 3/5 (§7) | New dimension — scored down from the blended 3/5 specifically because this pass confirmed the pipeline has never had a real automated end-to-end run |
| Observability | *(folded into Operational Readiness before)* | 3/5 (§8) | New dimension |
| AI architecture | *(not separately scored before)* | 5/5 (§9) | New dimension — the strongest-scoring dimension in this assessment |
| Multi-agent orchestration | *(not separately scored before)* | 3/5 (§10) | New dimension — surfaces NEW-001, the most significant new finding in this pass |
| **Overall (simple average across this assessment's 10 dimensions)** | **3.8/5** (5-dimension average, PBI-10-06) | **3.5/5** (10-dimension average) | **Not a regression.** The prior 5-dimension average and this 10-dimension average use different methodologies and are not directly comparable point-for-point. The decrease reflects a stricter, more granular assessment that separately scores 5 dimensions (Enterprise readiness, Scalability, DevOps, AI architecture, Multi-agent orchestration) the prior pass folded into broader categories — most notably Scalability (2/5), which the prior 5-dimension scoring never isolated. Security, the dimension that most directly drove the prior score, is unchanged at 4/5. |

**Why the methodology changed**: PBI-10-07 explicitly named 10 dimensions to reassess, several of
which (Scalability, DevOps, AI architecture, Multi-agent orchestration, Enterprise readiness) did
not exist as their own scored line item in the prior 5-dimension table. Scoring them separately is
more informative than folding them into "Operational Readiness"/"Architecture & Design," even
though it produces a lower blended number — the underlying facts did not get worse; they got
measured more precisely.

---

## 14. Production readiness — updated score and Go/No-Go

**Updated Production Readiness Score: 3.5/5** (10-dimension methodology, §13), superseding the
5-dimension 3.8/5 figure from `05_executive_summary.md` (2026-08-11, PBI-10-06) as the primary
number going forward — that document is updated in this same pass to reference this one.

| Intended use | Recommendation | Change from PBI-10-06 |
|---|---|---|
| Academic demonstration | **GO** | Unchanged |
| Internal DEV prototype | **GO** | Unchanged |
| Pilot with real users | **CONDITIONAL GO** | Unchanged in direction; NEW-001 (no confidence-based escalation) is a new consideration to disclose to any real-user pilot, given the domain (insurance) is exactly the "ambiguous/low-confidence/coverage-related" case CLAUDE.md's own Human-in-the-Loop principle names |
| Production | **CONDITIONAL — NO-GO until P1 items close** | Unchanged in direction; scalability (§4, no autoscale rule + per-process state) is now an explicitly named production blocker in its own right, not merely implied by RISK-008 |

### Final enterprise recommendation

This platform is in a materially stronger state than the pre-Entra-ID assessment: the single
finding that previously blocked every real-user-facing recommendation (authentication/IDOR) is
resolved and proven, not merely claimed, and the AI architecture and multi-agent routing
mechanics are genuinely well-built and test-verified. What this deeper, 10-dimension pass adds is
not new alarm about security — it is a more honest picture of two things the prior, narrower
review did not isolate: **this platform cannot currently scale beyond one replica** (no scale
rule exists, not just a conservative cap), and **one of its own named governance principles
(confidence-based human escalation) was never actually built**, only documented as an intention.
Neither is a security vulnerability. Both are exactly the kind of gap a genuine enterprise
architecture review should surface before a real production commitment — and both are cheap
relative to the authentication work already completed: a scale rule is a Bicep change once the
state-sharing question is answered, and the escalation gap can be closed either by building the
mechanism or by correcting the architecture document to stop claiming it exists. Recommended
sequencing: treat NEW-001 (escalation) as the next priority documentation-or-implementation
decision — it is a stated principle currently false on inspection — ahead of the pre-existing P1
hardening list (rate limiting, security headers, root containers, network isolation).

---

## Cross-references

- `00_project_inventory.md`, `01_architecture_review.md`, `02_security_review.md`,
  `03_code_quality_review.md`, `04_risk_register.md`, `05_executive_summary.md` — the PBI-10-06
  review set this assessment compares against and, where noted above, supersedes.
- [ADR-0007](../docs/Architecture/adr/0007-ai-governance-boundary.md) — the governance boundary
  this assessment's AI-architecture score (§9) and the Human-in-the-Loop gap (NEW-001) both bear
  on.
- [ADR-0010](../docs/Architecture/adr/0010-enterprise-authentication-entra-id.md) — the
  authentication decision record underlying §11's resolved-findings check.

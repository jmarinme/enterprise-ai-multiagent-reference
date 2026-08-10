# Sprint 08 — Architecture Review Remediation & Hardening

## Objective

Remediate the five remaining Architecture Review findings (`reports/review/01_architecture_review.md`)
that block final delivery: A-17 (hardening scope never executed), A-07 (no retry/circuit
breaker), A-08 (liveness-only health check), A-11 (no Azure Monitor alerting), A-16 (stray
repository file). No new business functionality; no redesign of Supervisor, Agents, RAG,
frontend, or conversation flows.

## Scope

- [x] PBI-08-01: Architecture Review Remediation & Hardening (A-07, A-08, A-11, A-16, A-17;
      A-10/OpenTelemetry deliberately NOT implemented — documented recommendation only, per
      this PBI's own explicit "do not expand scope into A-10 unless trivial" instruction).

## Out of scope

- A-02 (import namespace inconsistency), A-03 (Azure Functions drift — already resolved by
  Sprint 06/07), A-05 (no caching layer), A-06 (`@lru_cache` per-process scope), A-09
  (correlation ID — already positive/verified, preserved unchanged), A-10 (OpenTelemetry —
  recommendation documented, not implemented), A-12 through A-15 (all positive findings, no
  action needed) — none of these were named in this PBI's remediation list.
- Any change to Agent, Supervisor, PromptManager, RAG, Grounding, Tool business logic, or the
  frontend — confirmed via `git status`/`git diff`: every changed file is either a new
  observability/resilience primitive, a provider-adapter wrapper, a new test file, or Bicep.
- A real, live Azure OpenAI/Cosmos/AI Search failure injection — the resilience and readiness
  work is validated with fully mocked failures (matching this repository's existing testing
  convention — no production traffic exists to safely fail against).
- Manual DEV deployment — Azure DevOps owns deployment once CI/CD is operational (CLAUDE.md
  §7.1, Sprint 07). No `az deployment group create`/`az containerapp update` was run for this
  PBI's application-code changes; the new `monitor-alerts` Bicep module was validated
  (`az deployment group validate`/`what-if`, both read-only) but not deployed.

## Deliverables

- [x] **A-07 (Resilience)**: `src/core/resilience/` (retry-with-backoff + circuit breaker),
      integrated into all three external-call providers (`AzureOpenAIProvider`,
      `AzureAISearchProvider`, `CosmosConversationRepository`). 22 new tests.
- [x] **A-08 (Readiness)**: `GET /ready` alongside the unchanged `GET /health`; checks only the
      dependencies actually configured; new `LLMProvider.health_check()` Protocol method
      (Mock/Ollama/AzureOpenAI); reuses existing `ConversationRepository`/`KnowledgeRetriever`
      methods for the other two. 6 new tests.
- [x] **A-11 (Monitoring)**: `ops/bicep/modules/monitor-alerts.bicep` — one Action Group + three
      metric alerts (elevated error rate, high latency, availability), on metric names
      confirmed live against the real deployed resources, not guessed. Additive only;
      `az deployment group validate` succeeded against the real DEV resource group.
- [x] **A-16 (Hygiene)**: stray `tatus` file removed; no other accidental root-level artifacts
      found.
- [x] **A-17 (Hardening)**: `tests/conversational/test_prompt_injection_and_security_scenarios.py`
      (7 tests), `tests/e2e/test_load.py` (2 tests), fresh dependency/secret-scan evidence
      (`evidence/`), documented latency/cost-telemetry measurement methodology
      (`evidence/latency-and-cost-telemetry.md`), this validation documentation.
- [x] **Observability**: correlation ID propagation preserved unchanged (verified by a new
      dedicated test); OpenTelemetry adoption assessed and documented as a recommendation, not
      implemented (genuinely non-trivial — see `decisions.md`).

## Acceptance criteria

| Finding | Criterion | Evidence |
|---|---|---|
| A-07 | Retry with exponential backoff on transient failures; circuit breaker; never retries non-transient/business errors; tests | `src/core/resilience/{retry,circuit_breaker}.py`; integrated into 3 providers; `tests/unit/core/resilience/`, provider-specific resilience tests |
| A-08 | `/health` unchanged (liveness); new `/ready` (dependency readiness); safe (no secrets/exception text exposed); clear degraded/unready status; tests | `apps/api/src/api/routes/health.py`; `tests/unit/api/test_health.py` |
| A-11 | Minimal Azure Monitor alerting via Bicep; error rate, latency, availability covered; non-destructive | `ops/bicep/modules/monitor-alerts.bicep`; `az deployment group validate` succeeded; `what-if` showed 0 deletions/replacements |
| A-16 | Stray `tatus` file removed; no similar artifacts remain | `git status` shows `D tatus`; root directory listing reviewed |
| A-17 | Prompt-injection tests; lightweight load test; dependency/security scan evidence; latency/cost telemetry evidence or documented measurement; hardening validation doc | `tests/conversational/`, `tests/e2e/test_load.py`, `docs/sprint_08/evidence/` |

## Dependencies

- `reports/review/01_architecture_review.md` — the review this PBI resolves findings from.
- Sprint 07's `SecurityScan` stage (`pip-audit`/`npm audit`/`detect-secrets`) — reused directly
  for this PBI's dependency/security scan evidence, not reimplemented.
- CLAUDE.md §7.1 (Sprint 07) — Claude Code does not deploy; this PBI's Bicep change is validated
  but not applied.

## Risks

| Risk | Probability | Impact | Mitigation |
|---|---:|---:|---|
| Resilience/readiness logic validated only against mocked failures, never a real Azure outage | Accepted | Low-Medium | Matches this repository's existing testing convention throughout; no production traffic exists to safely fail against |
| `monitor-alerts.bicep` not yet applied to real Azure | Accepted, documented | Low | Validated (`validate`/`what-if`, both non-mutating); applying it is a separate, later action per CLAUDE.md §7.1 (Azure DevOps owns deployment) |
| OpenTelemetry (A-10) remains unimplemented | Accepted, explicitly in scope for this PBI | Low | Explicit instruction: "do not expand scope into A-10 unless trivial" — assessed as non-trivial, documented as a recommendation (`decisions.md`) |
| Prompt-injection test suite is a smoke-level set of scenarios, not an exhaustive red-team exercise | Accepted | Low | Matches "academic hardening" framing; scenarios chosen to verify existing structural guarantees, not to discover novel LLM jailbreaks (MockLLMProvider is content-agnostic by design) |

## Deliverable Log

<!-- Append entries. Do not remove previous entries. -->

PBI-08-01: See `decisions.md` and `validation.md` for the full writeup. Summary: added
`src/core/resilience/` (retry-with-backoff, circuit breaker), integrated into
`AzureOpenAIProvider`/`AzureAISearchProvider`/`CosmosConversationRepository` (22 new tests,
never retries non-transient errors — verified explicitly). Added `GET /ready` alongside
unchanged `GET /health`, checking only configured dependencies, never exposing secrets/exception
text (6 new tests); `LLMProvider` Protocol gained `health_check()`, implemented by all three
concrete providers. Added `ops/bicep/modules/monitor-alerts.bicep` (Action Group + 3 metric
alerts on live-confirmed metric names), wired additively into `main.bicep`, validated
(`az deployment group validate` succeeded, `what-if` confirmed non-destructive) but not deployed.
Removed the stray `tatus` file (A-16); no other accidental artifacts found. Added
`tests/conversational/test_prompt_injection_and_security_scenarios.py` (7 tests) and
`tests/e2e/test_load.py` (2 tests, 20-concurrent-request smoke load test). Re-ran Sprint 07's
security tooling (`pip-audit`, `npm audit --omit=dev`, `detect-secrets`) for fresh evidence — all
clean. Documented latency/cost-telemetry measurement methodology
(`evidence/latency-and-cost-telemetry.md`) rather than adding new Supervisor/Agent code, since
aggregating real token usage into the existing `supervisor_turn_latency` log line would require
threading `LLMUsage` through every `AgentResponse` — named as a scoped, explicit follow-up, not
implemented (would border on the "do not redesign... conversation flows" boundary). Assessed
OpenTelemetry adoption (A-10) as genuinely non-trivial (new dependencies, startup
instrumentation wiring, correlation-ID/trace-ID reconciliation) and documented a recommendation
instead of implementing it, per this PBI's own explicit scope boundary. Full regression: **612 backend tests passed, 2 skipped** — 37 of these are new this PBI (11
`src/core/resilience` unit tests; 3 `AzureOpenAIProvider`, 3 `AzureAISearchProvider`, and 5
`CosmosConversationRepository` resilience-integration tests; 6 `/ready` tests; 7 prompt-injection
scenarios; 2 load tests), see `validation.md` for the exact per-checkpoint counts. Ruff and mypy
clean on every touched file. No commit, no push, no deployment — awaiting review. — 2026-08-10
Evidence: `validation.md`, `decisions.md`, `evidence/`.

## Sprint validation

See `validation.md`.

## Sprint retrospective

Complete when closing the sprint:

- What worked:
- What did not:
- Technical debt:
- Security findings:
- Follow-up PBIs:

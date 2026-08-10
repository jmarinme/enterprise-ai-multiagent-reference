# 04 — Risk Register

Aggregates every finding from `01_architecture_review.md`, `02_security_review.md`, and
`03_code_quality_review.md`. Sorted by **Risk Score** descending.

Scoring rubric (as specified): CRITICAL×HIGH=10, HIGH×HIGH=8, HIGH×MEDIUM=6, MEDIUM×HIGH=5,
MEDIUM×MEDIUM=3, LOW×any=1-2. No CRITICAL-severity finding was identified in this review — every
concrete exploit path found (IDOR, unbounded input) has either a mitigating factor (synthetic
data only, UUID-space guessing difficulty) or requires a separately-realized precondition, which
placed it at HIGH rather than CRITICAL under this review's own "no CRITICAL without a clear,
concrete exploit path" rule.

"Blocks production?" is assessed against **a real TMX production deployment with real
policyholder data**, per this review's brief — not against this repository's own stated
DEV/academic scope, which the project itself never claimed was production-ready (CLAUDE.md §1).

| ID | Category | Title | Severity | Likelihood | Score | Blocks production? | Effort |
|---|---|---|---|---|---|---|---|
| RISK-001 | Security | No authentication mechanism exists (Entra ID planned, not implemented) | HIGH | HIGH | 8 | YES | Weeks |
| RISK-002 | Architecture | Sprint 05 "Hardening" scope (prompt-injection tests, dashboards, cost telemetry, load/resilience tests) per CLAUDE.md §14 has not been executed under any sprint | HIGH | HIGH | 8 | YES | Weeks |
| RISK-003 | Security | Concrete IDOR: `GET /conversations`/`GET /conversations/{id}` trust a client-supplied, unsigned `userId` with no session binding | HIGH | MEDIUM | 6 | YES | Days–Weeks (bundled with RISK-001 fix) |
| RISK-004 | Architecture | No retry-with-backoff or circuit breaker around any external call (Azure OpenAI, Cosmos, AI Search), despite CLAUDE.md principle #9 | MEDIUM | HIGH | 5 | CONDITIONAL | Days |
| RISK-005 | Code Quality | `tests/e2e/`/`tests/conversational/` are empty; automated conversational/E2E regression protection does not exist despite CLAUDE.md §11 requiring it and manual validation repeatedly finding real bugs it can't catch | MEDIUM | HIGH | 5 | CONDITIONAL | Weeks |
| RISK-006 | Security/CI | No dependency (SCA) or container-image vulnerability scanning anywhere in the CI pipeline; Python dependencies unpinned | MEDIUM | HIGH | 5 | CONDITIONAL | Hours–Days |
| RISK-007 | Observability | No Azure Monitor alerting/action groups configured despite telemetry being collected | MEDIUM | HIGH | 5 | CONDITIONAL | Days |
| RISK-008 | Architecture | Azure Functions / Durable Functions specified in CLAUDE.md §4/§5 are not used; Tools and the Claims workflow run in-process instead, with no ADR reconciling the deviation | MEDIUM | HIGH | 5 | NO (functionally sound, but needs an ADR per CLAUDE.md §1's own conflict-resolution rule) | Days (ADR) / Weeks (if re-architected) |
| RISK-009 | Security | Both Dockerfiles run as root (no `USER` directive) | MEDIUM | MEDIUM | 3 | CONDITIONAL | Hours |
| RISK-010 | Security | Web production image serves via `vite preview`, not a hardened static server | MEDIUM | MEDIUM | 3 | CONDITIONAL | Hours–Days |
| RISK-011 | Security | No HTTP security headers (CSP, HSTS, X-Content-Type-Options, X-Frame-Options) anywhere | MEDIUM | MEDIUM | 3 | CONDITIONAL | Hours |
| RISK-012 | Security | `ChatRequest.message` has no length bound — unauthenticated cost/DoS amplification vector against Azure OpenAI | MEDIUM | MEDIUM | 3 | CONDITIONAL | Hours |
| RISK-013 | Security | No application-layer rate limiting; APIM (the designated gateway) is disabled by default | MEDIUM | MEDIUM | 3 | CONDITIONAL | Hours (basic throttle) – Days (APIM) |
| RISK-014 | Architecture | OpenTelemetry (named in CLAUDE.md §5) is not actually used; structured logging + App Insights substitute for it | LOW | HIGH | 2 | NO | Days (if adopted) |
| RISK-015 | Code Quality | No Python dependency lockfile (`pyproject.toml` ranges only); frontend is correctly pinned | LOW | MEDIUM | 2 | NO | Hours |
| RISK-016 | Architecture | No Cosmos DB schema/migration strategy | LOW | MEDIUM | 2 | NO (low impact — synthetic data only today) | Days |
| RISK-017 | Architecture | `/health` is a static liveness-only probe; no downstream dependency (Cosmos/Azure OpenAI) readiness check | LOW | MEDIUM | 2 | NO | Hours |
| RISK-018 | Security | `upload_lead_document` Tool (CLAUDE.md §4.2 minimum inventory for Commercial Intake) not implemented | LOW | HIGH | 2 | CONDITIONAL (only if document upload is a required real-world capability) | Days |
| RISK-019 | Code Quality | No pre-commit hooks — quality gates are CI-only, local iteration has no fast gate | LOW | MEDIUM | 2 | NO | Hours |
| RISK-020 | Code Quality | API Dockerfile's hand-written pip-install list and `apps/api/pyproject.toml`'s declared dependencies are two independent, driftable sources of truth | LOW | LOW | 1 | NO | Hours |
| RISK-021 | Code Quality | Stray `tatus` file (accidental `git diff` dump) committed at repo root | LOW | N/A (already occurred) | 1 | NO | Minutes |
| RISK-022 | Code Quality | No global FastAPI exception handler (relies on Starlette's safe 500 default) | LOW | LOW | 1 | NO | Hours |
| RISK-023 | Architecture | Inconsistent Python import namespace at the API boundary (`src.`-prefixed vs. bare), a deliberate Dockerfile-driven tradeoff | LOW | LOW | 1 | NO | N/A (documented tradeoff, works as-is) |

## Positive controls (not risks — recorded here for completeness of the go/no-go picture)

These were explicitly verified in code, not just claimed in documentation, and materially offset
the risk items above:

- Layered architecture (Web → API → Supervisor → Agents → Tools/RAG → Cosmos) genuinely matches
  the stated design, verified via import-graph inspection, not just docstrings.
- Tool-call authorization (allow-list check before execution) is real and tested.
- Correlation-ID propagation is real and live-validated end-to-end.
- Core business truth (policies, claims, brokers, commissions) is never persisted to Cosmos DB —
  matches CLAUDE.md §4.3 exactly.
- No secrets found anywhere in source, config, or git history; `.gitignore` correctly excludes
  `.env`/keys/`secrets/`.
- Every Azure provider defaults to Managed Identity; API-key auth is opt-in only, via
  `SecretProvider`, never `os.environ` directly.
- RBAC posture is genuinely least-privilege — no subscription/RG-scoped `Contributor`/`Owner`
  anywhere in 15 Bicep files.
- CORS is correctly restrictive (explicit origins, no wildcard, `allow_credentials=False`).
- No XSS vectors found in the React frontend (`dangerouslySetInnerHTML` absent everywhere).
- CI/CD pipeline runs full tests + lint + type-check + IaC validation + gated deploy + real smoke
  tests on every deploy, with zero `continueOnError`/skipped-failure patterns found.
- 551 backend + 33 frontend tests passing as of the latest sprint; zero TODO/FIXME/HACK markers
  across 201 Python files.

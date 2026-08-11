# 02 — Security Review

Severity legend: **CRITICAL** (exploitable now, high impact) / **HIGH** / **MEDIUM** / **LOW** /
**INFO**. Every finding below cites the file/config key that evidences it; nothing here is
theoretical without a concrete code path shown.

## 3a. Secrets & credentials — GOOD

- No hardcoded secret, API key, password, or connection string found in any source or config
  file examined (`.env.example` all-blank; grepped `src/`, `apps/*/src/`, `ops/bicep/**`).
- `.gitignore` explicitly excludes `.env*` (keeping `!.env.example`), `*.pem`, `*.key`, `*.pfx`,
  `secrets/`.
- Every credential-shaped value is sourced from environment variables
  (`src/config/settings.py`, Pydantic Settings) or Azure Key Vault
  (`src/services/secret_store/azure_key_vault_secret_provider.py`), never embedded in code.
- CI runs `detect-secrets scan --all-files` as a hard gate (`azure-pipelines.yml`, `SecurityScan`
  stage) — a real, automated backstop, not just a manual claim.

**INFO** — well-managed exception: `pip-audit --ignore-vuln PYSEC-2026-1845` is explicitly
allow-listed in CI with an inline justification (pytest-only CVE, fixed only in a breaking pytest
9.x upgrade, `pytest` never ships in the deployed container). This is exactly how a suppressed
finding should be handled — documented, scoped, not silent — and is noted here as a positive
practice, not a risk.

## 3b. Authentication & authorization — the platform's single largest gap

- **No authentication mechanism exists anywhere in `apps/api/src/`.** Grepped for
  JWT/OAuth/Entra/Bearer-token validation middleware — the only matches are unrelated (Azure SDK
  client credentials for the app's *own* outbound calls to Azure OpenAI/AI Search, not inbound
  request authentication).
- Every endpoint (`POST /chat`, `GET /conversations`, `GET /conversations/{id}`) accepts a
  client-supplied `userId` string with zero verification (`apps/api/src/api/routes/chat.py`:
  `class ChatRequest(_CamelModel): ... user_id: str`; `conversations.py`:
  `user_id: str = Query(alias="userId")`).
- `GET /conversations/{conversationId}?userId=<any-string>` returns that user's full conversation
  history to *any* caller who supplies (or guesses) their `userId` — a textbook IDOR
  (`conversations.py::get_conversation`, no ownership check beyond the unauthenticated `userId`
  value used as the query key itself). Verified by reading the handler: it passes
  `user_id`/`conversation_id` straight to `repository.get_conversation(user_id, conversation_id)`
  with no comparison against any authenticated caller identity, because none exists.
- No admin/internal route exists to separately protect.
- This is a known, **intentionally deferred** gap for the academic implementation scope
  (CLAUDE.md §4.5 names Entra ID; `docs/sprint_00/security-baseline.md` §7 scopes it out for
  early sprints) — not a surprise, and not an implementation oversight. "Intentionally deferred"
  and "resolved" are different things: deferring the work does not change what the code currently
  does at runtime, so this finding is reported at full severity below, not softened for being
  planned.

**Severity: HIGH | Likelihood: HIGH** for both the missing authentication and the IDOR that
results from it. This score reflects **application control** — what the code itself guarantees,
independent of where it happens to be deployed today — and is the score that governs the
production Go/No-Go decision (`05_executive_summary.md`).

**Current-environment exposure, reported separately, does not change the score above.** The live
DEV Container App runs inside the Tokio Marine Mexico corporate Azure tenant/subscription, but
that tenant boundary governs *who can administer the Azure resources* (subscription RBAC), not
*who can call the public HTTP endpoint* — `enablePrivateNetworking=false` (confirmed live) means
the API's ingress is a normal public internet endpoint with no network ACL, IP allowlist, or
gateway auth in front of it. Reachability is therefore not meaningfully reduced by the
corporate-tenant framing, and likelihood of *technical* exploitation stays HIGH regardless of
context. What genuinely differs in the current DEV/academic environment is the *consequence*:
every record behind the API is synthetic demonstration data (`SYN-*`/`CUS-SYN-*` prefixes
throughout `src/services/tools/synthetic/provider.py`) — there is no real customer, policy, or
personal data to expose — and there is no real, indexed user base to make the endpoint an
attractive target. This is why the same finding can simultaneously support **GO for continued
DEV/academic use** and **NO-GO for production** (`05_executive_summary.md` §7): the underlying
gap is identical in both settings; only what there is to lose differs.

## 3c. OWASP Top 10 (2021) — systematic check

| # | Category | Finding | Severity |
|---|---|---|---|
| A01 | Broken Access Control | Confirmed IDOR (§3b). CORS is configuration-driven, never `*` (`main.py`: `allow_origins=settings.cors_allowed_origins_list`) — good. | HIGH |
| A02 | Cryptographic Failures | No plaintext-sensitive-data storage found (no PII exists). TLS is Azure Container Apps' own ingress default (not independently verified as enforced-only, no HSTS header set — see A05). No password hashing anywhere (no passwords exist — no local auth). | LOW |
| A03 | Injection | No SQL/NoSQL/command/LDAP/template injection surface found — no raw SQL exists (Cosmos SDK, parameterized by design), no `eval`/`exec`/`os.system`/`subprocess` call anywhere in `src/`/`apps/api/src/` (grepped, zero real hits — the only "eval(" text matches are in docstrings explicitly stating none is used), Jinja2-free custom prompt renderer (`src/prompts/renderer.py`, explicitly documents "no third-party templating engine, no eval()"). | INFO (none found) |
| A04 | Insecure Design | No rate limiting, no account lockout (no accounts exist), no password-reset flow (no passwords exist) — see A07/rate-limiting note below. | MEDIUM |
| A05 | Security Misconfiguration | No security-headers middleware (`CSP`/`HSTS`/`X-Frame-Options`/`X-Content-Type-Options`) anywhere in `apps/api/src/` — grepped, zero hits. Both Dockerfiles run as root (no `USER` directive in `apps/api/Dockerfile` or `apps/web/Dockerfile`). `apps/web/Dockerfile`'s production `CMD` is `npm run preview`, which Vite's own documentation states is not intended for production serving. Cosmos/Key Vault/AI Search/OpenAI all have `publicNetworkAccess: Enabled` in DEV (`enablePrivateNetworking=false` in `dev.bicepparam`) — internet-reachable at the network layer, mitigated by RBAC + Managed-Identity-only auth (`disableLocalAuth: true` on Cosmos, RBAC-only Key Vault, admin user disabled on ACR — all independently confirmed in Bicep), with a documented production remediation path already written (`docs/Architecture/adr/0002-vnet-private-endpoints-hardening.md`). | MEDIUM |
| A06 | Vulnerable & Outdated Components | `fastapi`, `pydantic`, `uvicorn`, React 18.3, TypeScript 5.5 are all current, actively-maintained major versions with no widely-known critical CVE at time of review. CI runs `pip-audit`/`npm audit` on every build (`SecurityScan` stage) with results published as build artifacts — a real, automated gate, not a point-in-time manual claim. No Python dependency lockfile exists (`pyproject.toml` uses `>=x,<y` ranges only), so the exact resolved version set is not reproducible build-to-build — a supply-chain reproducibility gap, not a known-vulnerability one. | LOW (current deps) / MEDIUM (no lockfile) |
| A07 | Identification & Authentication Failures | N/A — no authentication exists to fail (see A02/§3b). No MFA (no auth). No session mechanism (stateless `userId` per request). | Subsumed by §3b |
| A08 | Software & Data Integrity Failures | No deserialization of untrusted data found (Pydantic model validation only, strict typed parsing — not `pickle`/`yaml.load` on user input). Container images are built and pushed via `az acr build` in CI with commit/build-traceable tags (never `latest`, confirmed in `azure-pipelines.yml`'s own tagging convention and this session's own deployment, which used `dev-20260811024920-pbi0901`) — good image-integrity practice. No image signing/SBOM found. | LOW |
| A09 | Security Logging & Monitoring Failures | Structured JSON logs with correlation IDs exist and were independently re-verified live in this review. No explicit "failed auth attempt" logging exists (there is nothing to fail — no auth). 3 metric alerts (error rate, latency, availability) are now live (`monitor-alerts.bicep`, confirmed via `az resource list`) — a real improvement since the prior review's "no alerting" finding, though these are infra-health alerts, not security-event alerts (no alert fires on, e.g., a burst of 404s on `/conversations/{id}` that might indicate ID-guessing). | MEDIUM |
| A10 | SSRF | No user-controlled URL is ever fetched server-side — grepped for outbound HTTP calls keyed off request input, found none. Every outbound call target (Azure OpenAI endpoint, AI Search endpoint, Cosmos endpoint) is a fixed configuration value, never derived from a request. | INFO (none found) |

## 3d. Application-specific risks

- **Input validation**: Pydantic models validate shape/type on every endpoint (`ChatRequest`,
  etc.) — good baseline. **No length bound exists on `ChatRequest.message`**
  (`apps/api/src/api/routes/chat.py`, confirmed: plain `message: str`, no `Field(max_length=...)`).
  This is a known, already-documented gap — `tests/conversational/test_prompt_injection_and_security_scenarios.py::test_extremely_long_message_does_not_crash_or_hang`
  exists and explicitly documents "no new size limit was added... this test documents current
  behavior at a bounded size, not an unbounded stress test." A crude but real DoS surface: an
  arbitrarily large message body is currently accepted and forwarded to the LLM/Tool pipeline.
- **Output encoding**: this is a JSON API only (never server-rendered HTML) — confirmed by
  `tests/conversational/test_prompt_injection_and_security_scenarios.py::test_xss_shaped_message_is_returned_as_inert_json_text_not_executed`,
  which documents this boundary is real, not assumed. XSS responsibility correctly sits with
  `apps/web`'s own React rendering (React escapes by default; not independently re-audited for a
  `dangerouslySetInnerHTML` usage in this review — a scope gap).
- **File uploads**: none exist (`grep -rln "UploadFile\|multipart"` returned nothing) — no
  attack surface here at all.
- **Mass assignment**: Pydantic request models declare an explicit field allow-list by
  construction (no `**kwargs`/dict-passthrough pattern found) — a caller cannot set an
  undeclared field.
- **Rate limiting & DoS**: no rate-limiting library or middleware found anywhere
  (`slowapi`/custom — grepped, zero hits). Combined with the unbounded message length above, an
  unauthenticated caller can send unlimited large requests, each of which triggers a real Azure
  OpenAI call (cost exposure) with no per-caller throttle.
- **Dependency integrity**: `apps/web/package-lock.json` is present and committed (good); no
  Python equivalent lockfile exists (repeat of A06's finding).

## 3e. Infrastructure & deployment security

- **Containers run as root** in both `apps/api/Dockerfile` and `apps/web/Dockerfile` — no `USER`
  directive in either, confirmed by direct read. Unchanged from the prior review.
- **Ports**: `apps/api` exposes 8000, `apps/web` exposes 3000 — both minimal, single-purpose,
  matching each app's own actual listener; no additional/debug ports exposed.
- **No open debug port or admin interface** found.
- **HTTPS**: enforced at the Azure Container Apps ingress layer by platform default (not
  independently verified via a raw HTTP request in this review — a scope gap, not a
  contradiction of the claim).
- **No security headers** — repeat of A05.
- **Network isolation**: `enablePrivateNetworking=false` in DEV (repeat of A05) — a deliberate,
  ADR-documented DEV-scope choice (`docs/Architecture/adr/0001-networking-posture-and-vnet-deferral.md`),
  not an oversight, with RBAC/Managed-Identity as the compensating control.
- **RBAC/least-privilege — GOOD, re-verified**: Cosmos `disableLocalAuth: true`; Key Vault
  `enableRbacAuthorization: true`; ACR `adminUserEnabled: false`; a single user-assigned Managed
  Identity used throughout, confirmed live (`id-tmxap-dev`) — all independently confirmed in
  Bicep source, not just claimed.

## Summary count (feeds `04_risk_register.md`)

| Severity | Count |
|---|---|
| CRITICAL | 0 |
| HIGH | 2 (no authentication; the resulting IDOR) |
| MEDIUM | 5 (no rate limiting/message-length bound, security headers absent, root containers + non-production web server, no Python dependency lockfile, network isolation deferred-with-mitigation, security-event alerting absent) |
| LOW | 3 (TLS not independently re-verified, no image signing/SBOM, current-but-unpinned dependency versions) |
| INFO | 3 (well-managed CVE suppression, no injection surface found, no SSRF surface found) |

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

## 3b. Authentication & authorization — RESOLVED (Microsoft Entra ID, PBI-11-01 through PBI-11-01D)

This section previously reported the platform's single largest gap: no authentication anywhere
in `apps/api/src/`, and the resulting IDOR. Re-checked from scratch against the current
repository, not against the prior review's conclusions, per this review's own instruction not to
reuse them.

- **A real authentication mechanism now exists and is live in DEV.** `apps/api/src/api/auth/`
  (`validator.py`'s `EntraTokenValidator`, `jwks.py`'s `JwksProvider`, `dependency.py`'s
  `get_current_user`) validates, on every call to `POST /chat`, `GET /conversations`, and
  `GET /conversations/{id}`: RS256 signature (against Microsoft's live JWKS,
  `https://login.microsoftonline.com/common/discovery/v2.0/keys`), expiry, audience (exact match
  against `ENTRA_API_AUDIENCE`, the bare API client ID GUID — confirmed correct against a real
  live token, PBI-11-01D), and issuer (self-consistency check against the token's own `tid`,
  correct for a `/common` multi-tenant authority). `get_current_user` is a required FastAPI
  dependency on all three routes — confirmed by reading `apps/api/src/api/routes/chat.py` and
  `conversations.py` directly, not inferred.
- **`ChatRequest.user_id` and the `userId` query parameter are now deprecated, optional, and
  never read for authorization.** Confirmed by reading the route handlers: identity passed to
  `ConversationRepository` is exclusively `current_user.user_id` (derived from the validated
  token as `f"{tid}:{oid}"`), never the request body/query value. The old, vulnerable code path
  (`user_id: str` required field, used directly as the Cosmos partition key with no verification)
  no longer exists.
- **The IDOR is closed, and proven closed, not merely designed to be closed.**
  `tests/unit/api/test_auth.py` includes dedicated regression tests that mint two genuinely
  different Entra identities and confirm: (1) User B cannot read User A's conversation even when
  supplying User A's own old `userId` and real `conversationId` (`404`, not `200`); (2) User B's
  conversation list never includes User A's conversations; (3) two different authenticated
  identities get fully independent conversation histories. This is the concrete evidence this
  review requires — not a claim that the design should prevent IDOR, but a test that proves a
  simulated attack against the real code fails.
- **CORS was found broken for exactly this new authenticated flow during the same work
  (PBI-11-01C) and is now fixed and regression-tested.** `apps/api/src/main.py`'s
  `CORSMiddleware` `allow_headers` now explicitly includes `Authorization` (previously only
  `Content-Type`/`X-Correlation-ID`) — confirmed by reading `main.py` directly, and by
  `tests/unit/api/test_cors.py`'s dedicated preflight tests for both `/chat` and `/conversations`.
  This was a real defect found and fixed while bringing the new authentication flow to a working
  state, not a hypothetical.
- **No client secret was introduced anywhere.** The frontend (`apps/web/src/auth/`) uses OAuth2
  Authorization Code + PKCE via MSAL Browser/React — the standard, currently-recommended flow for
  a public client that cannot hold a secret; confirmed no client secret exists in
  `apps/web/`'s source or environment configuration (grepped, none found).
- **What remains true, unchanged from before**: no rate limiting exists on the now-authenticated
  endpoints (§3d) — a valid, authenticated caller can still send unlimited requests; no
  security-event alerting exists for authentication failures specifically (a burst of `401`s is
  not distinguished from any other error in the current alert rules, §3c A09). These are real,
  separate, still-open gaps — closing authentication does not close them, and this review does
  not claim it does.

**Severity: RESOLVED** (previously HIGH/HIGH for both the missing authentication and the
resulting IDOR). This reflects **application control** — what the code itself now guarantees,
independent of where it is deployed — verified by reading the current authentication code
directly and by the passing regression test suite cited above, not by re-asserting the prior
review's unresolved status. See `04_risk_register.md` (RISK-001, RISK-002) for the full
before/after evidence trail and [ADR-0010](../docs/Architecture/adr/0010-enterprise-authentication-entra-id.md)
for the architectural decision record.

## 3c. OWASP Top 10 (2021) — systematic check

| # | Category | Finding | Severity |
|---|---|---|---|
| A01 | Broken Access Control | IDOR resolved (§3b) — regression-tested proof two authenticated identities cannot read each other's conversations. CORS is configuration-driven, never `*` (`main.py`: `allow_origins=settings.cors_allowed_origins_list`), and now correctly allows `Authorization` on preflight (PBI-11-01C fix, §3b) — good. | LOW (resolved; no rate-limiting-based access control exists — see A04) |
| A02 | Cryptographic Failures | No plaintext-sensitive-data storage found (no PII exists). TLS is Azure Container Apps' own ingress default (not independently verified as enforced-only, no HSTS header set — see A05). No password hashing anywhere (no passwords exist — no local auth). | LOW |
| A03 | Injection | No SQL/NoSQL/command/LDAP/template injection surface found — no raw SQL exists (Cosmos SDK, parameterized by design), no `eval`/`exec`/`os.system`/`subprocess` call anywhere in `src/`/`apps/api/src/` (grepped, zero real hits — the only "eval(" text matches are in docstrings explicitly stating none is used), Jinja2-free custom prompt renderer (`src/prompts/renderer.py`, explicitly documents "no third-party templating engine, no eval()"). | INFO (none found) |
| A04 | Insecure Design | No rate limiting, no account lockout (no accounts exist), no password-reset flow (no passwords exist) — see A07/rate-limiting note below. | MEDIUM |
| A05 | Security Misconfiguration | No security-headers middleware (`CSP`/`HSTS`/`X-Frame-Options`/`X-Content-Type-Options`) anywhere in `apps/api/src/` — grepped, zero hits. Both Dockerfiles run as root (no `USER` directive in `apps/api/Dockerfile` or `apps/web/Dockerfile`). `apps/web/Dockerfile`'s production `CMD` is `npm run preview`, which Vite's own documentation states is not intended for production serving. Cosmos/Key Vault/AI Search/OpenAI all have `publicNetworkAccess: Enabled` in DEV (`enablePrivateNetworking=false` in `dev.bicepparam`) — internet-reachable at the network layer, mitigated by RBAC + Managed-Identity-only auth (`disableLocalAuth: true` on Cosmos, RBAC-only Key Vault, admin user disabled on ACR — all independently confirmed in Bicep), with a documented production remediation path already written (`docs/Architecture/adr/0002-vnet-private-endpoints-hardening.md`). | MEDIUM |
| A06 | Vulnerable & Outdated Components | `fastapi`, `pydantic`, `uvicorn`, React 18.3, TypeScript 5.5 are all current, actively-maintained major versions with no widely-known critical CVE at time of review. CI runs `pip-audit`/`npm audit` on every build (`SecurityScan` stage) with results published as build artifacts — a real, automated gate, not a point-in-time manual claim. No Python dependency lockfile exists (`pyproject.toml` uses `>=x,<y` ranges only), so the exact resolved version set is not reproducible build-to-build — a supply-chain reproducibility gap, not a known-vulnerability one. | LOW (current deps) / MEDIUM (no lockfile) |
| A07 | Identification & Authentication Failures | Resolved (§3b) — `EntraTokenValidator` validates signature/expiry/audience/issuer on every request; identity is `tid:oid`, never derived from anything client-supplied. MFA is delegated to Microsoft Entra ID's own tenant policy (outside this codebase, not independently verified in this review — a scope gap, not a code defect). No local session/password mechanism exists to fail (token-based, stateless). | LOW |
| A08 | Software & Data Integrity Failures | No deserialization of untrusted data found (Pydantic model validation only, strict typed parsing — not `pickle`/`yaml.load` on user input). Container images are built and pushed via `az acr build` in CI with commit/build-traceable tags (never `latest`, confirmed in `azure-pipelines.yml`'s own tagging convention and this session's own deployment, which used `dev-20260811024920-pbi0901`) — good image-integrity practice. No image signing/SBOM found. | LOW |
| A09 | Security Logging & Monitoring Failures | Structured JSON logs with correlation IDs exist and were independently re-verified live in this review. Authentication now exists (§3b), but a distinguishable "failed token validation" log signal / alert does not — `get_current_user` maps every validation failure to a generic `401` (correct, prevents information leakage to the caller) without a dedicated audit log line or metric, so a burst of `401`s (e.g., a credential-stuffing or token-tampering attempt) would not be distinguished from routine client errors in the current alert rules. 3 metric alerts (error rate, latency, availability) remain infra-health alerts, not security-event alerts. | MEDIUM |
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

Updated after re-running this review against the current repository — authentication (§3b) is no
longer a HIGH finding, resolved via Microsoft Entra ID (PBI-11-01 through PBI-11-01D). Every
other finding below was independently re-checked, not carried forward unchanged.

| Severity | Count |
|---|---|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 6 (no rate limiting/message-length bound — now applies to authenticated callers too, security headers absent, root containers + non-production web server, no Python dependency lockfile, network isolation deferred-with-mitigation, security-event/failed-auth alerting absent) |
| LOW | 3 (TLS not independently re-verified, no image signing/SBOM, current-but-unpinned dependency versions) |
| INFO | 3 (well-managed CVE suppression, no injection surface found, no SSRF surface found) |
| RESOLVED (since prior review) | 2 (missing authentication; the resulting IDOR — §3b) |

# 02 — Security Review

Reviewer persona: Security Engineer. Severity scale: CRITICAL / HIGH / MEDIUM / LOW / INFO.
No finding below is marked CRITICAL/HIGH without a concrete file:line exploit path.

**Framing reminder (per this review's brief):** Entra ID authentication is a documented,
explicitly-planned-but-not-yet-implemented gap (CLAUDE.md §4.5; `docs/sprint_00/
security-baseline.md` §7; `docs/sprint_04/decisions.md`, 2026-08-08 entries). It is reported
below with real severity because it is a genuine blocker for a **real TMX production**
deployment — but it is not a surprising discovery, and this review does not treat it as evidence
of carelessness. The concrete findings under A01/A07 below exist precisely *because* that gap is
real; they illustrate its practical consequence rather than duplicate it.

## 3a. Secrets & credentials

**Finding: none found — clean.** (INFO)

- `.gitignore:1-8` excludes `.env`, `.env.*` (keeping `!.env.example`), `*.pem`, `*.key`,
  `*.pfx`, `secrets/`, `.local/`.
- `git log --all --diff-filter=A --name-only | grep -iE '\.env$|\.pem$|\.key$|credentials'`
  returns no results — no secret-shaped file was ever added to history.
- A repository-wide regex scan for `(api[_-]?key|secret|password|connection[_-]?string)\s*[:=]\s*
  ["'][A-Za-z0-9+/_\-]{15,}["']` (case-insensitive) returns **zero matches** across the whole
  repository.
- `.env.example` contains only empty placeholders (`AZURE_OPENAI_API_KEY=`, etc.) — no default
  values that look like real secrets.
- Every Azure provider (`AzureOpenAIProvider`, `AzureAISearchProvider`,
  `CosmosConversationRepository`, `AzureKeyVaultSecretProvider`) defaults to Managed Identity
  (`DefaultAzureCredential`) and only reads a key through the `SecretProvider` abstraction when an
  explicit `*_USE_API_KEY` flag is set — never `os.environ` directly inside a provider, per the
  Sprint 01–03 deliverable logs' own stated design and this review's reading of
  `apps/api/src/api/dependencies.py:114-132,145-158`.

## 3b. AuthN / AuthZ

**Finding SEC-01 — No authentication mechanism exists (HIGH, documented/planned gap, not a
surprise).** No token validation, session, or API-key check exists anywhere in
`apps/api/src/`. `apps/api/src/main.py:12-36` wires only `CORSMiddleware` and
`CorrelationIdMiddleware` — no auth middleware. `POST /chat`
(`apps/api/src/api/routes/chat.py:27-30`) accepts a client-supplied `user_id: str` with no
verification whatsoever. This matches CLAUDE.md §4.5's stated plan (Entra ID, not yet built) and
is explicitly documented in `docs/sprint_00/security-baseline.md` §7 and restated as of
`docs/sprint_04/decisions.md` (2026-08-08, PBI-04-04 entry). **Reported here as a real production
blocker, not as an oversight.**

**Finding SEC-02 — Concrete IDOR on the conversation-history endpoints (HIGH, concrete exploit
path).** `GET /conversations` and `GET /conversations/{conversationId}`
(`apps/api/src/api/routes/conversations.py:76-92,95-117`) both take `user_id` as a plain query
parameter (`Query(alias="userId")`, lines 77 and 98) with **no binding to any authenticated
session** — the same unauthenticated trust model as `POST /chat`'s body field. Concretely: any
HTTP client that knows or guesses another user's `userId` (a `web-user-<uuid>` string generated
client-side and stored in `localStorage`, `apps/web/src/utils/userId.ts:6-21`, sent as plain
JSON/query text, never signed) can call
`GET /conversations/{id}?userId=<victim-id>` directly against the API (bypassing the Web app
entirely, which enforces nothing server-side anyway) and read that victim's full conversation
history, including whatever insurance details were discussed. This is the sharpest concrete
illustration of why SEC-01 is a real blocker, not just a theoretical one: the exploit path exists
today, requires no credentials, and is a straight IDOR (OWASP A01) once a `userId` value is known
or guessed. UUIDv4 space makes blind guessing impractical, but log/URL leakage, browser history,
or shoulder-surfing a `userId` are realistic disclosure paths for a demo/pilot deployment. **Not
CRITICAL** only because (a) all data behind it is synthetic per this project's own scope, and
(b) `userId` is a random UUID, not a small enumerable ID — but the *mechanism* is a textbook,
exploitable IDOR that would need fixing as part of, not separately from, SEC-01's remediation.

**Finding SEC-03 — Tool-level authorization is real and correctly enforced (positive control,
not a finding).** `ToolCallingOrchestrator` (per `docs/sprint_02/README.md` PBI-02-04) checks an
LLM-requested tool name against `ToolRegistry` existence and then against the calling Agent's own
`ToolCallingContext.allowed_tools` allow-list *before* `ToolExecutor` is ever invoked — an
unauthorized or unknown tool call fails with typed `error_type="unauthorized"`/`"unknown_tool"`
data, never a stack trace, and is never executed. This is a genuine, code-level authorization
boundary between what an LLM can request and what actually runs — the right design for
CLAUDE.md principle #2/#4 ("the LLM is not the source of truth... every business action must use
a deterministic, versioned Tool").

## 3c. OWASP Top 10 (2021) — explicit walkthrough

| # | Category | Finding | Severity |
|---|---|---|---|
| A01 | Broken Access Control | SEC-01, SEC-02 above | HIGH |
| A02 | Cryptographic Failures | No custom cryptography anywhere; all Azure auth delegated to Managed Identity/`DefaultAzureCredential`. Cosmos DB has `disableLocalAuth: true` (`ops/bicep/modules/cosmos-db.bicep`, per Sprint 00 PBI-00-05) — key-based auth is impossible even if desired. No finding. | INFO |
| A03 | Injection | No raw SQL; Cosmos accessed via the official SDK's typed query methods. No `eval()`/`exec()` found in any reviewed Python file. No shell-command construction from user input found in `apps/api/src/` or `src/`. Bicep/pipeline scripts quote all interpolated `az` CLI values. No finding. | INFO |
| A04 | Insecure Design | **Finding SEC-04**: `ChatRequest.message` (`apps/api/src/api/routes/chat.py:28`) is a bare `str` with no `max_length` (or any Pydantic `Field` constraint at all — contrast with `metadata`/`citations`/`tool_calls` which do use `Field(default_factory=...)` at lines 42/45/49, so the pattern for adding a constraint already exists in the same file). An attacker can submit an arbitrarily large `message`, which is then forwarded into the LLM prompt-rendering pipeline and, when `LLM_PROVIDER=azure_openai`, billed as real Azure OpenAI token usage — a low-cost, unauthenticated (per SEC-01) resource-exhaustion / cost-amplification vector. Deterministic Tool-calling for business actions itself (principle #2/#4) is **not** a finding — it is the correct, deliberate mitigation against LLM-hallucinated business facts, and is implemented as designed (SEC-03). | MEDIUM |
| A05 | Security Misconfiguration | **Finding SEC-05**: both `apps/api/Dockerfile` and `apps/web/Dockerfile` contain no `USER` directive — both containers run as **root** by default (verified: `grep -n "USER " apps/api/Dockerfile apps/web/Dockerfile` returns no match). **Finding SEC-06**: `apps/web/Dockerfile:16` serves the production build via `CMD ["npm", "run", "preview", ...]` — Vite's own documentation states `vite preview` is a local-only static-file previewer, not a production server (no gzip/brotli tuning, no cache-control strategy, no production security-header defaults) — a hardened static server (nginx/Caddy) behind the Container App would be the correct production pattern. **Finding SEC-07**: no HTTP security headers (`Content-Security-Policy`, `X-Content-Type-Options`, `Referrer-Policy`, `Strict-Transport-Security`, `X-Frame-Options`) are set anywhere — `apps/api/src/main.py:24-31` registers only `CORSMiddleware` and `CorrelationIdMiddleware`; there is no equivalent for the Web app either (no nginx config, no meta-tag CSP found). CORS itself is correctly configured (`allow_origins` from `Settings.cors_allowed_origins_list`, never `"*"`; `allow_credentials=False` since no cookie auth exists — `main.py:24-30`, `settings.py:19-28`) — this is a genuine positive control, not a finding. | MEDIUM |
| A06 | Vulnerable / Outdated Components | **Finding SEC-08**: no dependency or container vulnerability scanning exists anywhere in `azure-pipelines.yml` (all 8 stages reviewed in full — `BackendQuality` runs `pytest`/`ruff`/`mypy` only; no `pip-audit`, `safety`, `npm audit`, `bandit`, or container-image scan (Trivy/Grype/Microsoft Defender for Containers) step exists). Both `pyproject.toml` files use open version ranges (`fastapi>=0.115,<1`, etc.) rather than hash-pinned/locked versions — `apps/web/package-lock.json` is present and pins exact versions (good), but there is no Python equivalent (no `uv.lock`/`poetry.lock`/pip-compile output). This review did not (and could not, offline) check specific installed versions against live CVE databases — flagged as a **process gap** (no automated detection mechanism exists), not a claim that a specific CVE is currently present. | MEDIUM |
| A07 | Identification and Authentication Failures | Same root cause as SEC-01/SEC-02. `apps/web/src/utils/userId.ts:8-21` generates and stores the "identity" client-side with no server-side issuance, signing, or verification — architecturally this is *identification* only (a self-asserted label), never *authentication*. | HIGH |
| A08 | Software and Data Integrity Failures | No unsafe deserialization found — all API-facing models are typed Pydantic classes (`_CamelModel` pattern used consistently in `chat.py:23-24`, `conversations.py:33-34`). No `pickle`/`yaml.load` (unsafe) usage found; `pyyaml` is used only for prompt-file frontmatter parsing (`src/prompts/filesystem_provider.py`, not independently re-read this session, but referenced consistently as YAML-frontmatter parsing across Sprint 01 docs) — not verified here whether `yaml.safe_load` vs. `yaml.load` is used; **flagged as an unverified item**, not a confirmed finding, given this review's read budget. CI does not verify image provenance/signing before push to ACR. | LOW (unverified YAML loader call site; no signing) |
| A09 | Security Logging and Monitoring Failures | Structured logging + correlation ID propagation is real and verified (see `01_architecture_review.md` A-09) — a genuine positive control. But **Finding SEC-09** (=A-11 from the architecture review, cross-referenced here): no Azure Monitor alert rules/action groups exist in `ops/bicep/`, so a real attack or failure pattern in the logs would not page anyone automatically today. | MEDIUM |
| A10 | Server-Side Request Forgery (SSRF) | `OllamaLLMProvider` makes outbound HTTP calls to a configurable `OLLAMA_BASE_URL` (`.env.example`) — but this URL is an **operator-set environment variable**, never derived from end-user request input, so there is no user-controlled SSRF vector through it. No other outbound-URL-from-user-input pattern was found in the reviewed routes/agents/tools. No finding. | INFO |

## 3d. App-specific risks

- **Input validation (Pydantic coverage):** Every API request/response model reviewed
  (`ChatRequest`/`ChatResponse` in `chat.py`, `ConversationSummaryResponse`/
  `ConversationDetailResponse` in `conversations.py`) is a typed Pydantic model — good baseline
  coverage. The one concrete gap is SEC-04 (`ChatRequest.message` unbounded length).
  `conversation_id: str | None` also has no format validation (would accept any string, not just
  a UUID) — low risk, since it's only ever used as an opaque Cosmos document key, not
  interpolated into a query.
- **Output encoding / XSS (React):** `grep -rn "dangerouslySetInnerHTML|innerHTML|eval("
  apps/web/src` returns **zero matches**. React's default JSX text rendering escapes all
  interpolated content (message text, citations, agent names) — no finding.
- **File uploads:** CLAUDE.md §4.2 lists `upload_lead_document` as a minimum reference Tool for
  Commercial Intake. **Finding SEC-10**: it is **not implemented** —
  `src/services/tools/` contains 14 Tool files (`git ls-files`/`ls` confirmed); none is named
  `*upload*`/`*document*`, and `grep -rn "upload_lead_document" .` (excluding `.venv`) returns no
  matches anywhere in the repository. This is not a vulnerability in what exists (there is no
  file-upload code to have a vulnerability), but it means CLAUDE.md's own minimum Tool inventory
  for Commercial Intake is incomplete relative to spec — flagged here rather than in code quality
  because file-upload handling is exactly the kind of feature that, when eventually built, will
  need its own dedicated security review (content-type validation, size limits, storage
  isolation, malware scanning) that nothing in this codebase has yet had to address.
- **Mass assignment:** All API models use explicit field lists (no `**request.dict()`-style
  blind pass-through into a domain/persistence object was found in the reviewed routes) — no
  finding.
- **Rate limiting / DoS:** **Finding SEC-11**: no rate limiting exists at the application layer
  (no middleware in `main.py`) and Azure API Management — the platform's designated gateway layer
  for this per CLAUDE.md §4.5 — is explicitly disabled by default (`ENABLE_API_MANAGEMENT=false`
  in `.env.example`; consistent with `docs/sprint_00/README.md`'s "APIM... when enabled" framing
  as an optional, not-yet-turned-on layer). Combined with SEC-01 (no auth) and SEC-04 (unbounded
  message size), an unauthenticated caller can send unlimited, unbounded-size requests against a
  real Azure OpenAI-backed deployment with no application-layer throttle.
- **Lock files:** `apps/web/package-lock.json` is present and committed (good — reproducible
  frontend builds). No Python equivalent exists (see A06 above).

## 3e. Infrastructure & deployment security

- **Dockerfile non-root user:** Missing on both images — SEC-05 above.
- **Exposed ports:** `apps/api/Dockerfile:53` exposes `8000`, `apps/web/Dockerfile:15` exposes
  `3000` — both standard, non-privileged, intentional; no unexpected port exposure found.
- **Debug interfaces:** No `debug=True`/reload flags found in the production `CMD` of either
  Dockerfile (`uvicorn main:app --app-dir app_src --host 0.0.0.0 --port 8000` — no `--reload`).
- **HTTPS enforcement:** Not configured at the application layer, but Azure Container Apps
  terminates TLS and provides an HTTPS-only ingress FQDN by default at the platform level for
  every deployed app in this project (consistent with the `https://` URLs used throughout
  `docs/sprint_03/README.md`/`docs/sprint_04/README.md`'s live-validation evidence) — this is a
  platform-provided control, not an application one, and this review did not independently
  re-verify the live Container App's ingress TLS configuration (static review only). No app-level
  HTTP→HTTPS redirect exists, which is fine given the platform already enforces it.
- **Bicep RBAC posture (verified):** `grep -rn "Contributor|Owner" ops/bicep/` was run in full
  across the entire `ops/bicep/` tree. Every match is either (a) a role **name string** used
  correctly and narrowly — `Cosmos DB Data Contributor` (data-plane only, scoped to the Cosmos
  account, `ops/bicep/modules/cosmos-db.bicep:51,124-129`) or `Container Apps Contributor`
  (scoped to one specific Container App resource, never the resource group —
  `ops/bicep/modules/container-app.bicep:60-63,129-134`, with an explicit code comment stating
  this scoping is deliberate so "the pipeline identity cannot touch Cosmos DB/Key Vault/Azure
  OpenAI/AI Search/the registry's own management plane"), or (b) a doc-comment referencing the
  audited role list. **No subscription-, resource-group-, or management-plane-scoped
  `Contributor`/`Owner` role assignment exists anywhere in the IaC.** This is a genuine,
  verified least-privilege posture, consistent with `docs/Architecture/adr/0002-...md`'s own
  claimed RBAC audit.
- **Bicep networking posture (verified, matches ADR-0001/ADR-0002 exactly):**
  `docs/Architecture/adr/0001-networking-posture-and-vnet-deferral.md:22-44` documents — and this
  review's reading confirms is an accurate, not aspirational, description — that every data-plane
  resource defaults to public network access, gated only by identity/RBAC, with VNet/Private
  Endpoints implemented as an **opt-in** (`enablePrivateNetworking` param, per ADR-0002/PBI-03-04)
  that is `false` by default in `dev` (the only environment actually deployed) and `true` by
  default in `staging`/`prod` (never deployed). This is exactly the kind of documented,
  conscious, scoped tradeoff this review's brief asks to be reported accurately rather than
  rediscovered as a surprise — **it remains a real requirement to flip `enablePrivateNetworking`
  and re-validate before any real production traffic**, which is precisely what ADR-0001/0002
  already say.
- **Secret delivery to Container Apps:** Confirmed via the Sprint 03 deliverable log
  (PBI-03-02) that no new Container App secrets were needed beyond the pre-existing Application
  Insights connection-string Key Vault reference — every other configuration value set on the
  Container Apps is a plain, non-secret environment variable (endpoints, provider selection
  flags). Consistent with CLAUDE.md §9's "Secrets" standard.

## Security review summary

| ID | Finding | OWASP | Severity |
|---|---|---|---|
| SEC-01 | No authentication mechanism anywhere (documented, planned gap) | A07 | HIGH |
| SEC-02 | Concrete IDOR on `GET /conversations`/`GET /conversations/{id}` via unverified `userId` | A01 | HIGH |
| SEC-03 | Tool-call authorization allow-list correctly enforced before execution | — | Positive control |
| SEC-04 | `ChatRequest.message` has no length bound (cost/DoS amplification) | A04 | MEDIUM |
| SEC-05 | Both Dockerfiles run as root (no `USER` directive) | A05 | MEDIUM |
| SEC-06 | Web production image serves via `vite preview`, not a hardened static server | A05 | MEDIUM |
| SEC-07 | No HTTP security headers (CSP, HSTS, X-Content-Type-Options, etc.) anywhere | A05 | MEDIUM |
| SEC-08 | No SCA/container vulnerability scanning in CI; Python deps unpinned (no lockfile) | A06 | MEDIUM |
| SEC-09 | No Azure Monitor alerting configured despite telemetry being collected | A09 | MEDIUM |
| SEC-10 | `upload_lead_document` Tool (CLAUDE.md §4.2 minimum inventory) not implemented | — | LOW (nothing to exploit; inventory gap) |
| SEC-11 | No application-layer rate limiting; APIM (the designated gateway) disabled by default | A04/A05 | MEDIUM |
| — | No secrets found anywhere in source, config, or git history | — | INFO / clean |
| — | CORS correctly configured (explicit origins, no wildcard, no credentials) | — | Positive control |
| — | RBAC posture verified least-privilege, no Owner/subscription-scoped Contributor anywhere | — | Positive control |
| — | Networking posture (public access + RBAC) accurately matches its own ADRs, opt-in hardening exists | — | Documented, accepted tradeoff |
| — | No XSS vectors found in React frontend (`dangerouslySetInnerHTML` absent) | — | Positive control |

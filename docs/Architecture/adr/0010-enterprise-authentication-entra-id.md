# ADR-0010: Enterprise Authentication using Microsoft Entra ID

## Status

Accepted and implemented — 2026-08-11/12 (PBI-11-01, PBI-11-01A–D). Live and validated end to
end in DEV: real interactive Microsoft sign-in, a real Entra v2.0 access token accepted by the
API, and the pre-existing IDOR finding ([ADR-0007](0007-ai-governance-boundary.md)'s trust
boundary now backed by a real identity, not a client-supplied one) closed and regression-tested.
See `docs/Architecture/diagrams/authentication-request-flow.md` for the end-to-end request-flow
diagram this ADR's decisions produce.

## Context

Every prior architecture/security review of this platform ([ADR-0004](0004-conversation-store-selection.md)'s
conversation store, [ADR-0006](0006-provider-abstraction-pattern.md)'s provider pattern,
[ADR-0007](0007-ai-governance-boundary.md)'s AI governance boundary — none of which touched
identity) identified the same gap: `POST /chat`, `GET /conversations`, and
`GET /conversations/{id}` all trusted a client-supplied `userId` with no verification. This was
CLAUDE.md §4.5's own named target ("Frontend: Microsoft Entra ID with OAuth 2.0/OIDC. Backend:
token validation and role/scope checks.") — deferred, not accidental, but a real, reported
finding (`review/02_security_review.md` §3b, `RISK-001`/`RISK-002`) that a caller supplying or
guessing another user's `userId` could read that user's full conversation history: a textbook
IDOR, and the single blocker standing between this platform and any real-user pilot.

## Decision

### Frontend: MSAL React, authorization-code + PKCE

`@azure/msal-browser` + `@azure/msal-react` (`apps/web/src/auth/`). The App Registration uses
the `/common` authority deliberately — it supports both internal (`tokiomarine.com.mx`) and
external users, so no tenant ID is hardcoded anywhere in the frontend or backend. Sign-in is
`loginPopup()` requesting exactly one scope, this API's own delegated permission
(`api://67d95215-5a31-416a-99ab-5fe203fb7c32/access_as_user`) — never a client secret (SPAs
cannot hold one safely), never the implicit flow. Every API call acquires a token via
`acquireTokenSilent` first, falling back to an interactive popup only on
`InteractionRequiredAuthError` (`src/auth/getAccessToken.ts`).

### Frontend: dedicated redirect-bridge page (PBI-11-01B)

MSAL Browser 5.x completes popup and silent-iframe flows via a `BroadcastChannel`-based bridge,
not simple popup-location polling (confirmed directly from the installed package's source: `@azure/msal-browser/redirect-bridge`,
its own documented public export). The page loaded at `redirectUri` must call
`broadcastResponseToMainFrame()` to relay the response back to the window that opened it —
nothing does this automatically. This platform therefore registers a **second**, minimal,
dedicated redirect URI (`/auth-bridge.html` → `src/auth-bridge.ts`, a separate Vite build entry,
~1.25 kB) distinct from the SPA root, so a popup/silent-renewal never has to download and
evaluate the full ~350 kB application bundle just to relay one response — Microsoft's own
documented recommendation, not merely an optimization this platform chose independently.

### Backend: signature + expiry + audience + tenant-self-consistent issuer

`apps/api/src/api/auth/` — `JwksProvider` (injectable, no live network call in tests, same
provider-swap seam every other external dependency in this codebase uses,
[ADR-0006](0006-provider-abstraction-pattern.md)) fetches Microsoft's JWKS from
`https://login.microsoftonline.com/common/discovery/v2.0/keys`; `EntraTokenValidator` verifies
the token's RS256 signature against the matching published key, expiry (60s leeway), and
audience (`entra_api_audience` setting), then separately validates that `iss` matches
`https://login.microsoftonline.com/{tid}/v2.0` **for the token's own `tid` claim** — a
self-consistency check, not a single hardcoded issuer, which is the correct way to validate an
issuer under a `/common` multi-tenant authority (there is no single fixed tenant to compare
against). `get_current_user` (a required FastAPI dependency on all three protected routes) maps
any validation failure to a generic `401` — never a distinguishing error message.

### Audience: the bare API client ID GUID, not the Application ID URI (PBI-11-01D correction)

The original implementation configured `ENTRA_API_AUDIENCE` as the Application ID URI
(`api://67d95215-5a31-416a-99ab-5fe203fb7c32`) — the resource identifier the frontend *requests*
as a scope. Live evidence from a real, completed sign-in (`ver: 2.0`, `aud:
67d95215-5a31-416a-99ab-5fe203fb7c32`) proved this assumption wrong: **a real Entra v2.0 access
token's `aud` claim is the bare API client ID GUID**, not the Application ID URI — the URI is the
*requested resource*, not what ends up in the issued token. `entra_api_audience` was corrected
to the bare GUID (`src/config/settings.py`), with a regression test (`test_validator_rejects_the_legacy_application_id_uri_as_audience`)
proving the old (wrong) value is now explicitly rejected, not merely also-accepted alongside the
correct one — this platform issues only v2.0 tokens (confirmed live), so a single exact-match
audience is correct.

### CORS: `Authorization` explicitly allow-listed (PBI-11-01C correction)

`CORSMiddleware`'s `allow_headers` initially listed only `Content-Type` and
`X-Correlation-ID` — a browser preflight (`OPTIONS`) for a request carrying `Authorization`
failed before ever reaching FastAPI's own routing, let alone `get_current_user`. Fixed by adding
`Authorization` to the explicit allow-list (`apps/api/src/main.py`) — still never `allow_headers=["*"]`,
still the same restrictive, configuration-driven `allow_origins` this middleware already
enforced (PBI-04-02).

### Identity: `tid:oid`, never email

`AuthenticatedUser.user_id = f"{tid}:{oid}"` (`apps/api/src/api/auth/models.py`) — Entra's
stable, tenant-qualified object identifier, tenant-scoped so the same `oid` value from two
different tenants under `/common` can never collide. `name`/`preferred_username` are carried for
UI display only (`apps/web/src/components/Header.tsx`) and are never read for authorization
anywhere in `apps/api/src/api/routes/`.

### IDOR closure

`ChatRequest.user_id` and the `userId` query parameter on both `/conversations` routes are now
`Optional[str] = None`, explicitly marked `deprecated=True` in the OpenAPI schema, and **never
read** by either route handler — `current_user.user_id` (from the validated token) is the only
value ever passed to `ConversationRepository`. Proven, not just asserted:
`tests/unit/api/test_auth.py::test_user_b_cannot_read_user_as_conversation_even_supplying_user_as_old_userid`
mints two genuinely different Entra identities, has User B present User A's real old `userId`
*and* User A's real `conversationId`, and confirms `404` — the partition key used for every
read/write is always the server-derived identity, never a client-supplied one.

## Alternatives considered

- **A confidential-client (server-side) OAuth flow with a client secret held by the API.**
  Rejected: this is a genuine SPA — there is no server-rendered login page or backend session to
  hold a secret safely; a secret embedded in SPA JavaScript is not a secret. Authorization-code +
  PKCE is the OAuth 2.0-specified answer for exactly this case and is what Microsoft's own SPA
  App Registration platform type expects.
- **Implicit flow (`response_type=token`/`id_token`).** Rejected: deprecated by both OAuth 2.0
  Security Best Current Practice and Microsoft's own current guidance — tokens returned directly
  in a redirect URL fragment are more exposed (browser history, referrer leakage, no code
  exchange to bind the token to a verified client) than authorization-code + PKCE.
- **A hand-rolled OIDC client instead of MSAL.** Rejected: MSAL is Microsoft's own maintained
  library, handles token caching, silent renewal, and the popup/redirect-bridge protocol
  correctly (a protocol this ADR's own PBI-11-01B investigation showed is genuinely non-trivial —
  a hand-rolled client would have had to independently discover and implement the same
  `BroadcastChannel` bridge requirement). Reduces this platform's own security-critical surface
  area, consistent with CLAUDE.md §9's "no local authentication" instruction implying "use the
  identity platform's own client," not a bespoke reimplementation.
- **A hand-rolled JWT decode/verify instead of PyJWT.** Rejected: `PyJWT[crypto]` is a
  widely-used, actively-maintained library implementing RS256 verification correctly (constant-time
  comparison, proper ASN.1/JWK parsing via `cryptography`) — reimplementing signature
  verification by hand is exactly the kind of security-critical code this platform should not
  write itself.
- **Accepting both the Application ID URI and the bare GUID as valid audiences.** Rejected
  (explicitly, PBI-11-01D): this platform issues only v2.0 tokens (confirmed live, `ver=2.0`),
  and a v2.0 token's `aud` is always the bare GUID — accepting the URI too would mean accepting a
  token shape no genuine v2.0 flow can produce, widening the accepted set for no real
  compatibility need. If a genuine v1.0-token requirement is ever proven, that would warrant its
  own ADR amendment, not a silent broadening now.
- **A single, fixed `iss` string instead of a per-token, tenant-self-consistent check.**
  Rejected: there is no single fixed tenant under `/common` by design (the whole point of
  `/common` is to support any organization's users, per this ADR's own Context) — a fixed-string
  issuer check would either reject every legitimate multi-tenant sign-in or have to be disabled
  entirely, which is exactly the "weaken issuer validation" outcome CLAUDE.md's own security
  principles and this project's explicit instructions across PBI-11-01/01D forbid.
- **`allow_headers=["*"]`** (considered when diagnosing the CORS defect, PBI-11-01C). Rejected:
  no proven reason existed to widen beyond an explicit allow-list; adding exactly the one missing
  header (`Authorization`) closed the defect without loosening the origin/header posture this
  middleware otherwise enforces.

## Why OAuth2 Authorization Code + PKCE

PKCE (Proof Key for Code Exchange) binds the authorization code to the specific client instance
that requested it via a locally-generated code verifier/challenge pair, so an intercepted
authorization code cannot be redeemed by a different party — the standard, currently-recommended
mechanism for a public client (a SPA, which cannot hold a client secret) per OAuth 2.0 Security
BCP. MSAL Browser generates and verifies this automatically; confirmed live in the real captured
authorization request (`code_challenge_method=S256`, PBI-11-01A's own validation evidence).

## Why MSAL

See "Alternatives considered" above — the deciding factor is that MSAL is Microsoft's own
maintained implementation of a protocol (including the redirect-bridge mechanism PBI-11-01B
uncovered) that is genuinely non-trivial to reimplement correctly, and using it keeps this
platform's own code limited to configuration and token consumption, not protocol implementation.

## Why JWT

Entra ID issues OAuth 2.0/OIDC access tokens as JWTs (JSON Web Tokens) — this is Microsoft's own
token format for this flow, not a choice this platform made independently. A JWT is
self-contained (signature, claims, expiry all travel with the token), letting the API validate a
request without a network round-trip to Entra ID on every call (only the JWKS fetch is
networked, and that is cached).

## Why JWKS

The JSON Web Key Set is how a JWT's signature is actually verified without the API holding a
shared secret with Entra ID — Entra publishes its current RSA public signing keys at a
well-known endpoint (`/common/discovery/v2.0/keys`), keyed by `kid`, and rotates them
periodically. Fetching and caching this set (`JwksProvider`, 24h TTL, refreshed once on an
unrecognized `kid` to tolerate real key rotation) is the standard, correct way to verify an
RS256-signed token from an identity provider that manages its own signing keys.

## Why `tid` + `oid`

`oid` (object ID) is Entra's stable, immutable identifier for a specific user within a specific
tenant — unlike `email`/`preferred_username`, which a user or tenant admin can change, and unlike
`sub`, whose exact stability guarantees vary by token/app configuration. Because this platform's
authority is `/common` (any tenant), `oid` alone is insufficient — the same `oid` value is only
guaranteed unique **within** a tenant, so the tenant (`tid`) must be part of the authorization
key too. `f"{tid}:{oid}"` is therefore the minimal, stable, globally-unique identity key this
multi-tenant configuration requires — see [ADR-0004](0004-conversation-store-selection.md) for
why this value is what becomes the Cosmos DB partition key.

## Security implications

- **Positive**: the platform's single largest reported finding (`RISK-001`/`RISK-002`, HIGH/HIGH,
  score 8 in `review/04_risk_register.md`) is closed with real, regression-tested evidence — not
  merely implemented, but proven to actually prevent the specific IDOR scenario the finding
  described. No client secret exists anywhere in the SPA. Token validation never trusts an
  unsigned or wrong-audience/wrong-issuer token — every rejection path is regression-tested
  (`tests/unit/api/test_auth.py`, 24 tests).
- **Accepted, unchanged from before this ADR**: this platform still does not implement rate
  limiting, security response headers, or non-root containers (`RISK-003`/`004`/`009`) —
  authentication existing does not by itself close these unrelated findings; they remain
  tracked separately.
- **New, narrow surface**: the JWKS cache is per-process (matching this codebase's existing
  per-process caching posture, [ADR-0008](0008-resilience-strategy.md)'s own documented scope
  boundary) — a real key-rotation event is handled (refresh-on-unknown-`kid`), but a compromised
  Entra signing key would only be detected once Microsoft itself revokes/rotates it; this
  platform has no independent key-pinning beyond what JWKS itself provides.
- **Out of scope for this ADR, unresolved**: rate limiting, security headers, and network
  isolation (`enablePrivateNetworking=false` in DEV) remain separately tracked
  ([ADR-0001](0001-networking-posture-and-vnet-deferral.md),
  [ADR-0002](0002-vnet-private-endpoints-hardening.md)) — authentication answers "who is this
  caller," not "how much can one caller do" or "is the network itself reachable."

## Consequences

- Positive: `POST /chat`, `GET /conversations`, `GET /conversations/{id}` are genuinely
  identity-scoped now — the IDOR this platform's own security review flagged as its top
  production blocker is closed with test evidence, not just a design intent.
- Positive: the provider-abstraction pattern ([ADR-0006](0006-provider-abstraction-pattern.md))
  extended cleanly to authentication — `JwksProvider`/`EntraTokenValidator` are injectable, so
  the full validation logic (not a bypass) is exercised in tests via a fake JWKS key set, while
  business-flow tests use a lightweight, clearly-documented test-only identity override.
- Negative / accepted: every API call now requires a real, valid Entra token — local development
  and CI still default every OTHER provider to a zero-Azure-dependency mode
  ([ADR-0006](0006-provider-abstraction-pattern.md)), but there is currently no equivalent
  "mock auth" bypass for manual local testing against a running API instance; a developer needs
  a real (even a test-tenant) Entra sign-in, or must use the same test-only dependency-override
  pattern `tests/conftest.py` already establishes.
- Negative / accepted: two redirect URIs must now be registered and kept in sync in the App
  Registration (the SPA root and `/auth-bridge.html`) — a real, if small, additional piece of
  Entra-side configuration this platform's own Bicep does not manage (App Registrations are not
  a Bicep-managed resource type in this repository).
- Follow-up (not yet done, tracked in `review/04_risk_register.md`): a security-event alert (a
  burst of `401`s that might indicate credential-stuffing or ID-guessing) does not yet exist —
  only infra-health metric alerts do ([ADR-0008](0008-resilience-strategy.md) covers resilience,
  not security-event alerting).

## Relationship with other ADRs

- [ADR-0004](0004-conversation-store-selection.md) — the `tid:oid` identity this ADR establishes
  is exactly what becomes the Cosmos DB partition key for every conversation.
- [ADR-0006](0006-provider-abstraction-pattern.md) — `JwksProvider`/`EntraTokenValidator` follow
  the same injectable-provider pattern as every other external dependency in this codebase.
- [ADR-0007](0007-ai-governance-boundary.md) — this ADR supplies the authenticated identity that
  ADR-0007's deterministic routing/Tool-execution boundary now scopes every business action to;
  ADR-0007's own governance boundary (LLM never authorizes an action) is unchanged by this work.

## Review triggers

- Before adding a second App Registration or supporting a fixed (non-`/common`) tenant — revisit
  the issuer-validation approach.
- Before adding a confidential-client or service-to-service (non-user-delegated) API caller —
  that would need a different token-acquisition flow than this ADR's user-delegated
  authorization-code + PKCE.
- If Entra ever issues a v1.0 token to this application (not expected, not currently possible per
  live evidence) — revisit the single-audience-value decision above before accepting one.
- Before relying on `preferred_username`/`email` for anything beyond display — those claims are
  explicitly not part of the authorization identity today and this ADR's own reasoning for `oid`
  over email should be re-read first if that ever seems tempting.

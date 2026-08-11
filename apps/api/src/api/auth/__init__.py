"""Microsoft Entra ID (Azure AD) authentication for the API — PBI-11-01.

Validates Bearer access tokens issued by Entra ID for this platform's API and derives the
authoritative caller identity from the token's own claims. No client-supplied identity value
is ever trusted for authorization — see api.auth.dependency.get_current_user.

Audience (PBI-11-01D): this platform issues only v2.0 access tokens, confirmed live
(ver=2.0). A v2.0 token's `aud` claim is the bare API client ID GUID
(67d95215-5a31-416a-99ab-5fe203fb7c32) — NOT the "api://..." Application ID URI, which is
instead the *scope/resource identifier the frontend requests*
(src/auth/loginRequest.ts: api://67d95215-5a31-416a-99ab-5fe203fb7c32/access_as_user). See
src.config.settings.Settings.entra_api_audience.
"""

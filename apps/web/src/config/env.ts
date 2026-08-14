/** Application runtime configuration derived from Vite environment variables. */

/** `??` only falls back on `undefined`/`null` — it does not treat an empty or
 * whitespace-only string as "not set". The Docker build (`apps/web/Dockerfile`) declares
 * `VITE_ENTRA_REDIRECT_URI`/`VITE_ENTRA_POST_LOGOUT_REDIRECT_URI` as build ARGs that default to
 * an empty string when no override is supplied, so `import.meta.env.VITE_ENTRA_REDIRECT_URI`
 * gets inlined as the literal `""`, not `undefined` — `"" ?? fallback` then evaluates to `""`,
 * which MSAL passes straight to `new URL("")`, throwing `TypeError: Failed to construct 'URL':
 * Invalid URL` (observed as "Sign in with Microsoft" opening about:blank). This helper is the
 * fix: undefined, empty, and whitespace-only values are all treated as "not explicitly set" and
 * fall back to the runtime default; any other value (including one with incidental surrounding
 * whitespace) is preserved exactly as provided, never altered. */
function resolveOrFallback(value: string | undefined, runtimeFallback: () => string): string {
  if (value !== undefined && value.trim() !== "") {
    return value;
  }
  return runtimeFallback();
}

export const apiBaseUrl: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/** Microsoft Entra ID authentication (PBI-11-01). None of these values are secrets — a SPA
 * client ID, an authority URL, and an API scope/Application ID URI are all meant to be public
 * (the SPA never holds a client secret). Defaults match the confirmed DEV App Registration;
 * override per environment via the matching VITE_* build-time variable, same pattern as
 * apiBaseUrl above. */
export const entraAuthority: string =
  import.meta.env.VITE_ENTRA_AUTHORITY ?? "https://login.microsoftonline.com/common";
export const entraClientId: string =
  import.meta.env.VITE_ENTRA_CLIENT_ID ?? "67d95215-5a31-416a-99ab-5fe203fb7c32";
/** The delegated scope requested for API access tokens — this API's confirmed
 * Application ID URI + the "access_as_user" scope exposed under "Expose an API". */
export const entraApiScope: string =
  import.meta.env.VITE_ENTRA_API_SCOPE ??
  "api://67d95215-5a31-416a-99ab-5fe203fb7c32/access_as_user";
/** PBI-11-01B: must point at the dedicated MSAL redirect-bridge page (auth-bridge.html /
 * src/auth-bridge.ts), NOT the SPA root — MSAL Browser 5.x's popup and silent-iframe flows
 * complete via a BroadcastChannel bridge that only that page runs; loading the full SPA at the
 * redirect URI never calls it, so loginPopup()/acquireTokenSilent() would hang until timeout
 * and never resolve. Defaults to this SPA's own current origin + /auth-bridge.html — this
 * exact URL must be registered as a redirect URI on the App Registration (in addition to, not
 * instead of, the SPA root, which remains the app's own entry point). */
export const entraRedirectUri: string = resolveOrFallback(
  import.meta.env.VITE_ENTRA_REDIRECT_URI,
  () => `${window.location.origin}/auth-bridge.html`,
);
/** Where the user actually lands after signing out — the app itself, never the bridge page
 * above (that page has no UI and would leave the user on a blank screen post-logout). */
export const entraPostLogoutRedirectUri: string = resolveOrFallback(
  import.meta.env.VITE_ENTRA_POST_LOGOUT_REDIRECT_URI,
  () => window.location.origin,
);

/** PBI-13-01: a purely client-side kill switch for the Observability nav link/routes —
 * mirrors the backend's own OBSERVABILITY_ENABLED. Real authorization is always enforced
 * server-side (api.observability_access.require_observability_access); this only decides
 * whether the frontend bothers rendering the nav link and routes at all. Defaults to enabled,
 * matching the backend default. */
export const isObservabilityEnabled: boolean =
  (import.meta.env.VITE_OBSERVABILITY_ENABLED ?? "true") !== "false";

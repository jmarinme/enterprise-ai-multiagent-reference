/** Application runtime configuration derived from Vite environment variables. */

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
export const entraRedirectUri: string =
  import.meta.env.VITE_ENTRA_REDIRECT_URI ?? `${window.location.origin}/auth-bridge.html`;
/** Where the user actually lands after signing out — the app itself, never the bridge page
 * above (that page has no UI and would leave the user on a blank screen post-logout). */
export const entraPostLogoutRedirectUri: string =
  import.meta.env.VITE_ENTRA_POST_LOGOUT_REDIRECT_URI ?? window.location.origin;

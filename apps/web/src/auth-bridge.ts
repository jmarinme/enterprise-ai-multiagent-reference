/** Dedicated MSAL redirect-bridge entry point (PBI-11-01B).
 *
 * MSAL Browser 5.x's popup (`loginPopup`/`acquireTokenPopup`) and silent-iframe
 * (`acquireTokenSilent`) flows complete via a `BroadcastChannel`-based bridge: the page loaded
 * at the configured `redirectUri` must call `broadcastResponseToMainFrame()` to relay the raw
 * auth response back to the window/frame that initiated the request. Nothing does this
 * automatically just by constructing a `PublicClientApplication` — see
 * node_modules/@azure/msal-browser/src/redirect_bridge/index.ts and its public
 * `@azure/msal-browser/redirect-bridge` export.
 *
 * This is a genuinely separate, minimal page (not the SPA root) precisely so that a popup or a
 * hidden silent-renewal iframe never has to download/evaluate the full application bundle —
 * Microsoft's own documented recommendation for popup/iframe redirect targets.
 *
 * This page is never linked to or visited directly by a user; it is reached only as the
 * `redirectUri` MSAL itself navigates a popup/iframe to.
 */

import { broadcastResponseToMainFrame } from "@azure/msal-browser/redirect-bridge";

broadcastResponseToMainFrame().catch((error: unknown) => {
  // No user-facing UI here by design (see module docstring) — this is a diagnostic trace only,
  // visible in the popup/iframe's own devtools console if the bridge itself fails.
  console.error("MSAL redirect bridge failed:", error);
});

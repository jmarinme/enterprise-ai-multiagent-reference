/** MSAL configuration for Microsoft Entra ID authentication (PBI-11-01).
 *
 * Authority is intentionally /common (not a fixed tenant) — this App Registration supports
 * both internal and external users; MSAL and Entra ID determine sign-in/consent per user,
 * this app never hardcodes or assumes a tenant ID.
 */

import type { Configuration } from "@azure/msal-browser";
import { LogLevel } from "@azure/msal-browser";
import {
  entraAuthority,
  entraClientId,
  entraPostLogoutRedirectUri,
  entraRedirectUri,
} from "../config/env";

export const msalConfig: Configuration = {
  auth: {
    clientId: entraClientId,
    authority: entraAuthority,
    // PBI-11-01B: redirectUri is the dedicated bridge page (see config/env.ts) — used for the
    // interactive popup and silent-iframe flows. postLogoutRedirectUri is deliberately
    // different: after sign-out there is no bridge handshake to complete, so the user should
    // land on the real app, not the bridge page's blank screen.
    redirectUri: entraRedirectUri,
    postLogoutRedirectUri: entraPostLogoutRedirectUri,
  },
  cache: {
    // sessionStorage (not localStorage): a token compromised via XSS is scoped to the current
    // tab/session rather than persisting indefinitely across browser restarts — the standard,
    // more conservative MSAL SPA cache choice for this platform's synthetic-but-still-real
    // authentication flow.
    cacheLocation: "sessionStorage",
  },
  system: {
    loggerOptions: {
      loggerCallback: (level, message, containsPii) => {
        if (containsPii) {
          return;
        }
        if (level === LogLevel.Error) {
          console.error(message);
        }
      },
      logLevel: LogLevel.Warning,
    },
  },
};

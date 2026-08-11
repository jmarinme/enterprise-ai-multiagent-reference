/** The delegated scope requested at sign-in and for every access-token acquisition
 * (PBI-11-01) — this API's own confirmed scope, never a client secret, never Microsoft
 * Graph's default scope (which would carry the wrong audience for this API).
 */

import type { PopupRequest } from "@azure/msal-browser";
import { entraApiScope } from "../config/env";

export const loginRequest: PopupRequest = {
  scopes: [entraApiScope],
};

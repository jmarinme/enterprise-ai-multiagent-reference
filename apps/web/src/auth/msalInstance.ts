/** The single, process-wide MSAL PublicClientApplication instance (PBI-11-01). Must be
 * initialized (msalInstance.initialize()) before it is used — see main.tsx.
 */

import { PublicClientApplication } from "@azure/msal-browser";
import { msalConfig } from "./msalConfig";

export const msalInstance = new PublicClientApplication(msalConfig);

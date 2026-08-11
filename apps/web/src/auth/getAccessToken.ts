/** Acquires an access token for this API's confirmed delegated scope (PBI-11-01): silent
 * acquisition first (refreshes from MSAL's own cache, no user interaction), falling back to
 * an interactive popup only when silent acquisition genuinely cannot succeed (e.g. the first
 * time, or after the refresh token itself has expired) — never eagerly interactive.
 */

import type { AccountInfo, IPublicClientApplication } from "@azure/msal-browser";
import { InteractionRequiredAuthError } from "@azure/msal-browser";
import { loginRequest } from "./loginRequest";

export async function getAccessToken(
  instance: IPublicClientApplication,
  account: AccountInfo,
): Promise<string> {
  try {
    const result = await instance.acquireTokenSilent({ ...loginRequest, account });
    return result.accessToken;
  } catch (error) {
    if (error instanceof InteractionRequiredAuthError) {
      const result = await instance.acquireTokenPopup({ ...loginRequest, account });
      return result.accessToken;
    }
    throw error;
  }
}

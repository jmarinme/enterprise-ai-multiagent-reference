/** Polls the API foundation endpoints once on mount and exposes connectivity state. */

import { useEffect, useState } from "react";
import { fetchHealth, fetchVersion } from "../api/client";
import type { VersionResponse } from "../api/client";

export type ApiConnectivity = "checking" | "connected" | "disconnected";

export interface ApiStatus {
  connectivity: ApiConnectivity;
  version: string | null;
  /** Full build/deployment traceability payload (PBI-14-06), null until a successful
   * GET /version response arrives. */
  apiVersionInfo: VersionResponse | null;
}

export function useApiStatus(): ApiStatus {
  const [status, setStatus] = useState<ApiStatus>({
    connectivity: "checking",
    version: null,
    apiVersionInfo: null,
  });

  useEffect(() => {
    let cancelled = false;

    async function checkStatus(): Promise<void> {
      try {
        await fetchHealth();
        const version = await fetchVersion();
        if (!cancelled) {
          setStatus({ connectivity: "connected", version: version.version, apiVersionInfo: version });
        }
      } catch {
        if (!cancelled) {
          setStatus({ connectivity: "disconnected", version: null, apiVersionInfo: null });
        }
      }
    }

    void checkStatus();

    return () => {
      cancelled = true;
    };
  }, []);

  return status;
}

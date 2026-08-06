/** Polls the API foundation endpoints once on mount and exposes connectivity state. */

import { useEffect, useState } from "react";
import { fetchHealth, fetchVersion } from "../api/client";

export type ApiConnectivity = "checking" | "connected" | "disconnected";

export interface ApiStatus {
  connectivity: ApiConnectivity;
  version: string | null;
}

export function useApiStatus(): ApiStatus {
  const [status, setStatus] = useState<ApiStatus>({ connectivity: "checking", version: null });

  useEffect(() => {
    let cancelled = false;

    async function checkStatus(): Promise<void> {
      try {
        await fetchHealth();
        const version = await fetchVersion();
        if (!cancelled) {
          setStatus({ connectivity: "connected", version: version.version });
        }
      } catch {
        if (!cancelled) {
          setStatus({ connectivity: "disconnected", version: null });
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

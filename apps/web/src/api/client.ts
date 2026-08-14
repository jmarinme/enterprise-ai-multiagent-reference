/** Typed client for the read-only foundation endpoints exposed by apps/api. */

import { apiBaseUrl } from "../config/env";

export interface HealthResponse {
  status: string;
}

export interface VersionResponse {
  name: string;
  version: string;
  environment: string;
  /** Build/deployment traceability (PBI-14-06) — see apps/api/src/api/routes/version.py. */
  app_version: string;
  build_number: string;
  commit_sha: string;
  component: string;
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`);
  if (!response.ok) {
    throw new Error(`Request to ${path} failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}

export function fetchHealth(): Promise<HealthResponse> {
  return getJson<HealthResponse>("/health");
}

export function fetchVersion(): Promise<VersionResponse> {
  return getJson<VersionResponse>("/version");
}

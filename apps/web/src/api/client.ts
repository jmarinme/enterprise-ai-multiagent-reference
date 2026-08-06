/** Typed client for the read-only foundation endpoints exposed by apps/api. */

import { apiBaseUrl } from "../config/env";

export interface HealthResponse {
  status: string;
}

export interface VersionResponse {
  name: string;
  version: string;
  environment: string;
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

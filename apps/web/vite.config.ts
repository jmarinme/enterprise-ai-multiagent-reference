import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// PBI-08-02: environment-driven allowlist for Vite's preview-server Host-header check
// (VITE_PREVIEW_ALLOWED_HOSTS, comma-separated). Read via process.env — this file runs in
// Node.js as Vite's own config/CLI process, not bundled application code (that's the only
// place import.meta.env's browser-facing VITE_* inlining applies), so process.env is the
// correct, standard way to read it here. Defaults to the same known-good Azure Container Apps
// wildcard suffix this already used, so no env var is required for existing behavior to keep
// working unchanged — this only adds the *option* to override it later (e.g. a future
// production custom domain) without another code change; no Bicep/Container App env var is
// wired for it yet (out of PBI-08-02's own explicit "do not deploy Bicep" scope).
const allowedHostsEnv = process.env.VITE_PREVIEW_ALLOWED_HOSTS;
const previewAllowedHosts = allowedHostsEnv
  ? allowedHostsEnv
      .split(",")
      .map((host) => host.trim())
      .filter(Boolean)
  : [".azurecontainerapps.io"];

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
  },
  preview: {
    host: true,
    port: 3000,
    // Vite 5's preview server rejects any request whose Host header isn't localhost/127.0.0.1
    // or explicitly allow-listed (DNS-rebinding protection). Azure Container Apps' ingress
    // forwards the original public FQDN as the Host header, so without this the deployed DEV
    // web app returns "Blocked request. This host (...) is not allowed." for every request —
    // confirmed live during PBI-04-02's frontend inspection, and again during PBI-08-02's own
    // investigation (root cause there was a stale deployed image, not this config — see
    // docs/sprint_08/decisions.md). A leading-dot suffix match (Vite's documented
    // wildcard-domain syntax) covers any Container Apps environment's randomly-generated FQDN
    // suffix without hardcoding this specific one, so a future environment recreation with a
    // new suffix does not require another code change.
    allowedHosts: previewAllowedHosts,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/setupTests.ts",
  },
});

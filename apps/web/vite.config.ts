import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

const rootDir = fileURLToPath(new URL(".", import.meta.url));

// PBI-08-02: environment-driven allowlist for Vite's preview-server Host-header check
// (VITE_PREVIEW_ALLOWED_HOSTS, comma-separated). Read via process.env — this file runs in
// Node.js as Vite's own config/CLI process, not bundled application code (that's the only
// place import.meta.env's browser-facing VITE_* inlining applies), so process.env is the
// correct, standard way to read it here. Defaults to the same known-good Azure Container Apps
// wildcard suffix this already used, so no env var is required for existing behavior to keep
// working unchanged — this only adds the *option* to override it later (e.g. a future
// production custom domain) without another code change; no Bicep/Container App env var is
// wired for it yet (out of PBI-08-02's own explicit "do not deploy Bicep" scope).
//
// The explicit DEV FQDN below is deliberately listed alongside the wildcard, not instead of
// it: the wildcard already matches it (`hostname.endsWith(".azurecontainerapps.io")` — verified
// against Vite 5.4.21's own preview-server host check), so this is belt-and-suspenders, not a
// second mechanism. Root cause of the live "Blocked request" failure was never a missing
// allowedHosts entry — it was a stale deployed Web image predating the wildcard fix (the
// pipeline's DeployDev stage only rebuilds/redeploys the Web Container App when apps/web
// changed since the immediately-preceding commit; several recent main-branch merges did not
// touch apps/web, so the previously-built image kept running). This exact-host entry is a
// harmless, explicit safety net for this specific DEV environment regardless of that
// deploy-skip behavior or any future Vite change to wildcard-suffix matching.
const allowedHostsEnv = process.env.VITE_PREVIEW_ALLOWED_HOSTS;
const previewAllowedHosts = allowedHostsEnv
  ? allowedHostsEnv
      .split(",")
      .map((host) => host.trim())
      .filter(Boolean)
  : [
      ".azurecontainerapps.io",
      "ca-tmxap-dev-web.bluemushroom-e2f74836.eastus2.azurecontainerapps.io",
    ];

export default defineConfig({
  plugins: [react()],
  // Multi-page build (PBI-11-01B): auth-bridge.html is a genuinely separate, minimal MSAL
  // redirect-bridge entry point (see src/auth-bridge.ts) — a popup/silent-iframe auth flow
  // must never have to download and evaluate the full SPA bundle just to relay its response.
  build: {
    rollupOptions: {
      input: {
        main: resolve(rootDir, "index.html"),
        authBridge: resolve(rootDir, "auth-bridge.html"),
      },
    },
  },
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

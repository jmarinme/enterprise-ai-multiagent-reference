import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

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
    // confirmed live during PBI-04-02's frontend inspection. A leading-dot suffix match
    // (Vite's documented wildcard-domain syntax) covers any Container Apps environment's
    // randomly-generated FQDN suffix without hardcoding this specific one, so a future
    // environment recreation with a new suffix does not require another code change.
    allowedHosts: [".azurecontainerapps.io"],
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/setupTests.ts",
  },
});

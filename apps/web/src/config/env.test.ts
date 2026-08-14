import { afterEach, describe, expect, it, vi } from "vitest";

/** Regression tests for the empty-string Entra redirect URI bug (hotfix): `??` only falls back
 * on `undefined`/`null`, not on an empty or whitespace-only string, which is exactly what the
 * Docker build's default (unset) VITE_ENTRA_REDIRECT_URI/VITE_ENTRA_POST_LOGOUT_REDIRECT_URI
 * ARGs produce. Each case re-imports ./env fresh (via vi.resetModules + dynamic import) so the
 * module-level `const` exports are re-evaluated against a freshly stubbed import.meta.env,
 * mirroring how Vite actually inlines these values at build time.
 */

async function importEnvWithStubbedRedirectUris(overrides: {
  redirectUri?: string;
  postLogoutRedirectUri?: string;
}) {
  vi.resetModules();
  if (overrides.redirectUri !== undefined) {
    vi.stubEnv("VITE_ENTRA_REDIRECT_URI", overrides.redirectUri);
  }
  if (overrides.postLogoutRedirectUri !== undefined) {
    vi.stubEnv("VITE_ENTRA_POST_LOGOUT_REDIRECT_URI", overrides.postLogoutRedirectUri);
  }
  return import("./env");
}

describe("entraRedirectUri", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("falls back to the runtime origin + /auth-bridge.html when undefined", async () => {
    const env = await importEnvWithStubbedRedirectUris({});

    expect(env.entraRedirectUri).toBe(`${window.location.origin}/auth-bridge.html`);
  });

  it("falls back to the runtime origin + /auth-bridge.html when an empty string", async () => {
    const env = await importEnvWithStubbedRedirectUris({ redirectUri: "" });

    expect(env.entraRedirectUri).toBe(`${window.location.origin}/auth-bridge.html`);
  });

  it("falls back to the runtime origin + /auth-bridge.html when whitespace-only", async () => {
    const env = await importEnvWithStubbedRedirectUris({ redirectUri: "   " });

    expect(env.entraRedirectUri).toBe(`${window.location.origin}/auth-bridge.html`);
  });

  it("preserves a valid explicit URL exactly as provided", async () => {
    const explicit = "https://custom.example.com/auth-bridge.html";

    const env = await importEnvWithStubbedRedirectUris({ redirectUri: explicit });

    expect(env.entraRedirectUri).toBe(explicit);
  });
});

describe("entraPostLogoutRedirectUri", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("falls back to the runtime origin when undefined", async () => {
    const env = await importEnvWithStubbedRedirectUris({});

    expect(env.entraPostLogoutRedirectUri).toBe(window.location.origin);
  });

  it("falls back to the runtime origin when an empty string", async () => {
    const env = await importEnvWithStubbedRedirectUris({ postLogoutRedirectUri: "" });

    expect(env.entraPostLogoutRedirectUri).toBe(window.location.origin);
  });

  it("falls back to the runtime origin when whitespace-only", async () => {
    const env = await importEnvWithStubbedRedirectUris({ postLogoutRedirectUri: "  \t " });

    expect(env.entraPostLogoutRedirectUri).toBe(window.location.origin);
  });

  it("preserves a valid explicit URL exactly as provided", async () => {
    const explicit = "https://custom.example.com/";

    const env = await importEnvWithStubbedRedirectUris({ postLogoutRedirectUri: explicit });

    expect(env.entraPostLogoutRedirectUri).toBe(explicit);
  });
});

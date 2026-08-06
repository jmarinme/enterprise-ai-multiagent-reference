import { describe, expect, it, vi, afterEach } from "vitest";
import { fetchHealth, fetchVersion } from "./client";

describe("api client", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("fetchHealth resolves with the parsed health payload", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "ok" }),
    } as Response);

    const result = await fetchHealth();

    expect(result).toEqual({ status: "ok" });
  });

  it("fetchVersion resolves with the parsed version payload", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ name: "tmx", version: "0.1.0", environment: "local" }),
    } as Response);

    const result = await fetchVersion();

    expect(result).toEqual({ name: "tmx", version: "0.1.0", environment: "local" });
  });

  it("throws when the API responds with a non-ok status", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 } as Response);

    await expect(fetchHealth()).rejects.toThrow("Request to /health failed with status 500");
  });
});

import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { Header } from "./Header";

describe("Header", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("shows Connected and the API version when the API responds", async () => {
    globalThis.fetch = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/health")) {
        return Promise.resolve({ ok: true, json: async () => ({ status: "ok" }) } as Response);
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ name: "tmx", version: "0.1.0", environment: "local" }),
      } as Response);
    });

    render(<Header />);

    await waitFor(() => expect(screen.getByText("Connected")).toBeInTheDocument());
    expect(screen.getByText("API v0.1.0")).toBeInTheDocument();
  });

  it("shows Disconnected when the API is unreachable", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error("network error"));

    render(<Header />);

    await waitFor(() => expect(screen.getByText("Disconnected")).toBeInTheDocument());
  });
});

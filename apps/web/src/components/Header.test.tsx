import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { AccountInfo } from "@azure/msal-browser";
import { Header } from "./Header";

interface HeaderTestProps {
  account: AccountInfo;
  onSignOut: () => void;
  showObservabilityNav: boolean;
}

function renderHeader(props: Partial<HeaderTestProps> = {}) {
  return render(
    <MemoryRouter>
      <Header
        account={fakeAccount}
        onSignOut={vi.fn()}
        showObservabilityNav={false}
        {...props}
      />
    </MemoryRouter>,
  );
}

const fakeAccount: AccountInfo = {
  homeAccountId: "test-home-account-id",
  environment: "login.microsoftonline.com",
  tenantId: "11111111-1111-1111-1111-111111111111",
  username: "test.user@example.com",
  name: "Test User",
  localAccountId: "test-local-account-id",
} as AccountInfo;

describe("Header", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("shows Conectado when the API responds", async () => {
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

    renderHeader();

    await waitFor(() => expect(screen.getByText("Conectado")).toBeInTheDocument());
  });

  it("shows Sin conexión when the API is unreachable", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error("network error"));

    renderHeader();

    await waitFor(() => expect(screen.getByText("Sin conexión")).toBeInTheDocument());
  });

  it("displays the authenticated account's name (PBI-11-01) — display only, never an authorization key", () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: "ok" }) } as Response);

    renderHeader();

    expect(screen.getByText("Test User")).toBeInTheDocument();
  });

  it("calls onSignOut when Cerrar sesión is clicked", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: "ok" }) } as Response);
    const onSignOut = vi.fn();
    renderHeader({ onSignOut });

    screen.getByRole("button", { name: "Cerrar sesión" }).click();

    expect(onSignOut).toHaveBeenCalledTimes(1);
  });

  it("hides the Observability nav when showObservabilityNav is false (default)", () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: "ok" }) } as Response);

    renderHeader();

    expect(screen.queryByText("Observability")).not.toBeInTheDocument();
  });

  it("shows the Observability nav link when showObservabilityNav is true", () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: "ok" }) } as Response);

    renderHeader({ showObservabilityNav: true });

    expect(screen.getByText("Observability")).toBeInTheDocument();
    expect(screen.getByText("Chat")).toBeInTheDocument();
  });
});

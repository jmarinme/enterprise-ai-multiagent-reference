import { describe, expect, it, vi, afterEach } from "vitest";
import { ConversationRequestError, getConversation, listConversations } from "./conversations";

describe("listConversations", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("requests GET /conversations with the access token as a Bearer header", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [
        {
          conversationId: "conv-1",
          title: "Quiero reportar un accidente.",
          status: "active",
          currentAgent: "ClaimsAgent",
          createdAt: "2026-08-08T10:00:00Z",
          updatedAt: "2026-08-08T10:05:00Z",
        },
      ],
    } as Response);
    globalThis.fetch = fetchMock;

    const result = await listConversations("test-access-token");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/conversations");
    expect(url).not.toContain("userId");
    expect((init.headers as Record<string, string>).Authorization).toBe(
      "Bearer test-access-token",
    );
    expect(result).toHaveLength(1);
    expect(result[0].title).toBe("Quiero reportar un accidente.");
  });

  it("throws a ConversationRequestError with only the status on a non-ok response", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 } as Response);

    await expect(listConversations("test-access-token")).rejects.toBeInstanceOf(
      ConversationRequestError,
    );
  });
});

describe("getConversation", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("requests GET /conversations/{id} with the access token as a Bearer header", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        conversationId: "conv-1",
        title: "Quiero reportar un accidente.",
        status: "active",
        currentAgent: "ClaimsAgent",
        messages: [
          { role: "user", content: "Quiero reportar un accidente.", createdAt: "2026-08-08T10:00:00Z" },
        ],
        createdAt: "2026-08-08T10:00:00Z",
        updatedAt: "2026-08-08T10:05:00Z",
      }),
    } as Response);
    globalThis.fetch = fetchMock;

    const result = await getConversation("test-access-token", "conv-1");

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/conversations/conv-1");
    expect(url).not.toContain("userId");
    expect((init.headers as Record<string, string>).Authorization).toBe(
      "Bearer test-access-token",
    );
    expect(result.messages).toHaveLength(1);
    expect(result.messages[0].role).toBe("user");
  });

  it("throws a ConversationRequestError with status 404 when the conversation is missing", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404 } as Response);

    try {
      await getConversation("test-access-token", "missing-conv");
      throw new Error("expected getConversation to reject");
    } catch (error) {
      expect(error).toBeInstanceOf(ConversationRequestError);
      expect((error as ConversationRequestError).status).toBe(404);
    }
  });
});

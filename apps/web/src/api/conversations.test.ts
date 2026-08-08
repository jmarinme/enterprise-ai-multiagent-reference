import { describe, expect, it, vi, afterEach } from "vitest";
import { ConversationRequestError, getConversation, listConversations } from "./conversations";

describe("listConversations", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("requests GET /conversations with the userId as a query parameter", async () => {
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

    const result = await listConversations("web-user-123");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain("/conversations?userId=web-user-123");
    expect(result).toHaveLength(1);
    expect(result[0].title).toBe("Quiero reportar un accidente.");
  });

  it("throws a ConversationRequestError with only the status on a non-ok response", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 } as Response);

    await expect(listConversations("web-user-123")).rejects.toBeInstanceOf(ConversationRequestError);
  });
});

describe("getConversation", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("requests GET /conversations/{id} with the userId as a query parameter", async () => {
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

    const result = await getConversation("web-user-123", "conv-1");

    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain("/conversations/conv-1?userId=web-user-123");
    expect(result.messages).toHaveLength(1);
    expect(result.messages[0].role).toBe("user");
  });

  it("throws a ConversationRequestError with status 404 when the conversation is missing", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404 } as Response);

    try {
      await getConversation("web-user-123", "missing-conv");
      throw new Error("expected getConversation to reject");
    } catch (error) {
      expect(error).toBeInstanceOf(ConversationRequestError);
      expect((error as ConversationRequestError).status).toBe(404);
    }
  });
});

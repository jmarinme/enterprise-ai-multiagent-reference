import { describe, expect, it, vi, afterEach } from "vitest";
import { ChatRequestError, sendChatMessage } from "./chat";

describe("sendChatMessage", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("maps the request correctly for a first turn (no conversationId)", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        conversationId: "conv-1",
        agent: "ClaimsAgent",
        intent: "CLAIMS",
        response: "Could you provide your policy number?",
        citations: [],
        groundingMetadata: null,
        toolCalls: [],
      }),
    } as Response);
    globalThis.fetch = fetchMock;

    await sendChatMessage({ accessToken: "test-access-token", message: "I want to report an accident." });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/chat");
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>).Authorization).toBe(
      "Bearer test-access-token",
    );
    const body = JSON.parse(init.body as string);
    expect(body).toEqual({ message: "I want to report an accident." });
    expect(body).not.toHaveProperty("conversationId");
    expect(body).not.toHaveProperty("userId");
  });

  it("includes conversationId in the request body for a follow-up turn", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        conversationId: "conv-1",
        agent: "ClaimsAgent",
        intent: "CLAIMS",
        response: "Thank you.",
        citations: [],
        groundingMetadata: null,
        toolCalls: [],
      }),
    } as Response);
    globalThis.fetch = fetchMock;

    await sendChatMessage({
      accessToken: "test-access-token",
      message: "SYN-POL-0001",
      conversationId: "conv-1",
    });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body).toEqual({
      message: "SYN-POL-0001",
      conversationId: "conv-1",
    });
  });

  it("resolves with the full typed response, including citations and groundingMetadata", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        conversationId: "conv-2",
        agent: "ClaimsAgent",
        intent: "CLAIMS",
        response: "Here is what I found.",
        citations: [
          {
            reference: { referenceId: "1", chunkId: "KB-CLAIMS-0001" },
            documentId: "KB-CLAIMS-0001",
            title: "After-Hours Claim Reporting Procedure",
            section: null,
            sourcePath: "configs/knowledge_base/claims_after_hours_procedure.md",
            score: 0.5,
          },
        ],
        groundingMetadata: { retrievedCount: 2, citationCount: 1, topK: 2, isGrounded: true },
        toolCalls: [],
      }),
    } as Response);

    const result = await sendChatMessage({ accessToken: "test-access-token", message: "What documents do I need?" });

    expect(result.conversationId).toBe("conv-2");
    expect(result.citations).toHaveLength(1);
    expect(result.citations[0].documentId).toBe("KB-CLAIMS-0001");
    expect(result.groundingMetadata?.isGrounded).toBe(true);
  });

  it("throws a ChatRequestError with only the status on a non-ok response", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ detail: "Internal Server Error: Traceback (most recent call last)..." }),
    } as Response);

    await expect(sendChatMessage({ accessToken: "test-access-token", message: "hello" })).rejects.toBeInstanceOf(
      ChatRequestError,
    );

    try {
      await sendChatMessage({ accessToken: "test-access-token", message: "hello" });
    } catch (error) {
      expect(error).toBeInstanceOf(ChatRequestError);
      expect((error as ChatRequestError).status).toBe(500);
      // Never leaks the raw response body/stack trace into the error's own message.
      expect((error as ChatRequestError).message).not.toContain("Traceback");
    }
  });
});

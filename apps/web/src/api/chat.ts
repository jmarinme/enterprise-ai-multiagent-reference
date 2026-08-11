/** Typed client for POST /chat — the platform's single conversational entry point.
 *
 * Mirrors apps/api/src/api/routes/chat.py's ChatRequest/ChatResponse contract exactly (camelCase
 * on the wire). Only fields the current contract actually defines are typed here — no
 * speculative fields.
 */

import { apiBaseUrl } from "../config/env";

export interface CitationReference {
  referenceId: string;
  chunkId: string;
}

export interface Citation {
  reference: CitationReference;
  documentId: string;
  title: string;
  section: string | null;
  sourcePath: string | null;
  score: number;
}

export interface GroundingMetadata {
  retrievedCount: number;
  citationCount: number;
  topK: number;
  isGrounded: boolean;
}

export interface ToolCallResult {
  callId: string;
  toolName: string;
  success: boolean;
  // data/error/errorType exist on the wire contract but are deliberately not surfaced in the
  // UI beyond toolName/success — data may carry business fields not meant for casual display,
  // and error text, while safe (never a stack trace, per ToolCallResult's own backend
  // docstring), is kept out of the minimal chat view to stay demo-simple.
  error?: string | null;
  errorType?: string | null;
}

export interface ChatResponse {
  conversationId: string;
  agent: string;
  intent: string;
  response: string;
  citations: Citation[];
  groundingMetadata: GroundingMetadata | null;
  toolCalls: ToolCallResult[];
}

export interface SendChatMessageOptions {
  /** The caller's Entra ID access token (PBI-11-01) — sent as `Authorization: Bearer
   * <accessToken>`. This is now the platform's sole source of authorization identity; no
   * userId field is sent on the wire at all. */
  accessToken: string;
  message: string;
  conversationId?: string | null;
}

/** Thrown for a non-2xx /chat response. Carries only the HTTP status — never the response
 * body, so a raw backend error/stack trace can never reach UI error display. */
export class ChatRequestError extends Error {
  readonly status: number;

  constructor(status: number) {
    super(`Chat request failed with status ${status}`);
    this.status = status;
  }
}

export async function sendChatMessage({
  accessToken,
  message,
  conversationId,
}: SendChatMessageOptions): Promise<ChatResponse> {
  const response = await fetch(`${apiBaseUrl}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify({
      message,
      ...(conversationId ? { conversationId } : {}),
    }),
  });

  if (!response.ok) {
    throw new ChatRequestError(response.status);
  }

  return (await response.json()) as ChatResponse;
}

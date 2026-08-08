/** Typed client for GET /conversations, GET /conversations/{conversationId} — backs the
 * ChatGPT-style history sidebar (PBI-04-04). Mirrors
 * apps/api/src/api/routes/conversations.py's response contracts exactly (camelCase on the
 * wire).
 */

import { apiBaseUrl } from "../config/env";

export interface ConversationSummary {
  conversationId: string;
  title: string;
  status: string;
  currentAgent: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ConversationMessage {
  role: "user" | "assistant" | "system";
  content: string;
  createdAt: string;
}

export interface ConversationDetail {
  conversationId: string;
  title: string;
  status: string;
  currentAgent: string | null;
  messages: ConversationMessage[];
  createdAt: string;
  updatedAt: string;
}

/** Thrown for a non-2xx response. Carries only the HTTP status — never the response body. */
export class ConversationRequestError extends Error {
  readonly status: number;

  constructor(status: number) {
    super(`Conversation request failed with status ${status}`);
    this.status = status;
  }
}

export async function listConversations(userId: string): Promise<ConversationSummary[]> {
  const response = await fetch(`${apiBaseUrl}/conversations?userId=${encodeURIComponent(userId)}`);
  if (!response.ok) {
    throw new ConversationRequestError(response.status);
  }
  return (await response.json()) as ConversationSummary[];
}

export async function getConversation(
  userId: string,
  conversationId: string,
): Promise<ConversationDetail> {
  const response = await fetch(
    `${apiBaseUrl}/conversations/${encodeURIComponent(conversationId)}?userId=${encodeURIComponent(userId)}`,
  );
  if (!response.ok) {
    throw new ConversationRequestError(response.status);
  }
  return (await response.json()) as ConversationDetail;
}

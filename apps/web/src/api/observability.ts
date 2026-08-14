/** Typed client for GET /observability/summary, /observability/conversations,
 * /observability/conversations/{conversationId}, /observability/runs/{runId} (PBI-13-01).
 * Mirrors apps/api/src/api/routes/observability.py's response contracts exactly (camelCase on
 * the wire) — same pattern as api/conversations.ts.
 */

import { apiBaseUrl } from "../config/env";

export interface SummaryKpis {
  conversationCount: number | null;
  runCount: number | null;
  successRate: number | null;
  averageLatencyMs: number | null;
  totalInputTokens: number | null;
  totalOutputTokens: number | null;
  totalEstimatedCostUsd: number | null;
}

export interface ConversationSummaryRow {
  conversationId: string;
  userId: string;
  createdAt: string;
  updatedAt: string;
  status: string | null;
  primaryDomain: string | null;
  messageCount: number | null;
  runCount: number;
  totalInputTokens: number;
  totalOutputTokens: number;
  // PBI-14-03: None/null once any contributing run's cost is genuinely unknown — never a
  // fabricated 0. See src/domain/observability.py's ConversationSummary docstring.
  totalEstimatedCostUsd: number | null;
  operationalQualityScore: number | null;
  businessOutcome: string | null;
  lastMessagePreview: string | null;
}

export interface ConversationListResult {
  items: ConversationSummaryRow[];
  total: number;
  skip: number;
  limit: number;
}

export interface RunToolCall {
  callId: string;
  toolName: string;
  success: boolean;
  errorType: string | null;
  latencyMs: number | null;
}

export interface RunDetail {
  runId: string;
  conversationId: string;
  messageId: string | null;
  traceId: string | null;
  userId: string;
  createdAt: string;
  detectedIntent: string | null;
  intentConfidence: number | null;
  selectedAgent: string | null;
  routingReason: string | null;
  toolCalls: RunToolCall[];
  model: string | null;
  inputTokens: number | null;
  outputTokens: number | null;
  estimatedCostUsd: number | null;
  pricingSnapshotVersion: string | null;
  totalLatencyMs: number | null;
  iterations: number | null;
  stoppedDueToMaxIterations: boolean | null;
  stoppedDueToTimeout: boolean | null;
  finalStatus: string | null;
  errorCategory: string | null;
}

export interface ConversationMessageRow {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  createdAt: string;
  runId: string | null;
}

export interface ConversationDetailResult {
  summary: ConversationSummaryRow;
  messages: ConversationMessageRow[];
  runs: RunDetail[];
}

export interface ObservabilityFilters {
  userId?: string;
  agent?: string;
  status?: string;
  dateFrom?: string;
  dateTo?: string;
  search?: string;
}

/** Thrown for a non-2xx response. Carries only the HTTP status — never the response body,
 * same convention as ChatRequestError/ConversationRequestError. */
export class ObservabilityRequestError extends Error {
  readonly status: number;

  constructor(status: number) {
    super(`Observability request failed with status ${status}`);
    this.status = status;
  }
}

function authHeaders(accessToken: string): HeadersInit {
  return { Authorization: `Bearer ${accessToken}` };
}

function filtersToQuery(filters: ObservabilityFilters): string {
  const params = new URLSearchParams();
  if (filters.userId) params.set("userId", filters.userId);
  if (filters.agent) params.set("agent", filters.agent);
  if (filters.status) params.set("status", filters.status);
  if (filters.dateFrom) params.set("dateFrom", filters.dateFrom);
  if (filters.dateTo) params.set("dateTo", filters.dateTo);
  if (filters.search) params.set("search", filters.search);
  return params.toString();
}

export async function getSummaryKpis(
  accessToken: string,
  filters: ObservabilityFilters = {},
): Promise<SummaryKpis> {
  const query = filtersToQuery(filters);
  const response = await fetch(`${apiBaseUrl}/observability/summary${query ? `?${query}` : ""}`, {
    headers: authHeaders(accessToken),
  });
  if (!response.ok) {
    throw new ObservabilityRequestError(response.status);
  }
  return (await response.json()) as SummaryKpis;
}

export async function listObservabilityConversations(
  accessToken: string,
  filters: ObservabilityFilters = {},
  pagination: { skip?: number; limit?: number } = {},
): Promise<ConversationListResult> {
  const params = new URLSearchParams(filtersToQuery(filters));
  if (pagination.skip !== undefined) params.set("skip", String(pagination.skip));
  if (pagination.limit !== undefined) params.set("limit", String(pagination.limit));
  const query = params.toString();
  const response = await fetch(
    `${apiBaseUrl}/observability/conversations${query ? `?${query}` : ""}`,
    { headers: authHeaders(accessToken) },
  );
  if (!response.ok) {
    throw new ObservabilityRequestError(response.status);
  }
  return (await response.json()) as ConversationListResult;
}

export async function getObservabilityConversation(
  accessToken: string,
  conversationId: string,
): Promise<ConversationDetailResult> {
  const response = await fetch(
    `${apiBaseUrl}/observability/conversations/${encodeURIComponent(conversationId)}`,
    { headers: authHeaders(accessToken) },
  );
  if (!response.ok) {
    throw new ObservabilityRequestError(response.status);
  }
  return (await response.json()) as ConversationDetailResult;
}

export async function getRun(accessToken: string, runId: string): Promise<RunDetail> {
  const response = await fetch(`${apiBaseUrl}/observability/runs/${encodeURIComponent(runId)}`, {
    headers: authHeaders(accessToken),
  });
  if (!response.ok) {
    throw new ObservabilityRequestError(response.status);
  }
  return (await response.json()) as RunDetail;
}

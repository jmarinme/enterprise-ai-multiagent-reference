# ADR-0012 — Business/Agentic Observability Persistence Model

## Status

Accepted (PBI-13-01, Phase 1).

## Context

PBI-13-01 requires a Multi-Agent Observability module: a dashboard showing conversations, runs
(one per processed message), ReAct/tool-call execution metadata, tokens, estimated cost,
latency, and (Phase 2) deterministic quality signals — backed by real persisted data, never
demo/hardcoded values.

The existing conversation store (`src/services/conversation_store/`, ADR-0004) already
persists chat history: one `Conversation` document per conversation in the `conversations`
Cosmos container, partition key `/userId`, with an embedded, ordered `messages` array. This is
correct and sufficient for the chat experience itself, but is a poor fit for run-level
observability data for three concrete reasons:

1. **Write pattern.** A conversation document is read-modify-written on every turn today
   (`append_message`). Adding one more sub-document (a run record) per turn to the *same*
   document would mean re-writing the entire embedded message history — including on a long
   conversation — just to add one small run record. That is real write amplification and RU
   cost, not merely a style preference.
2. **Document-size ceiling.** Cosmos DB caps a single document at 2 MB. A conversation with
   many turns, each turn also carrying full tool-call/token/timeline detail embedded in the
   same document, moves meaningfully closer to that ceiling for no reason connected to the
   chat experience itself.
3. **Query shape.** The observability dashboard's two core read patterns — "list/aggregate
   across many conversations, optionally across many users" (V1 `all_authenticated`, PBI-13-01
   §16) and "get every run for one conversation" — are both read patterns the `conversations`
   container was never designed for (`list_conversations(user_id)` is deliberately scoped to
   one partition/one user).

## Decision

Do **not** extend the `conversations` container's document schema, and do **not** create three
new containers. Add exactly **one** new Cosmos container, `observability_runs`, holding two
document "kinds" distinguished by a `docType` field:

- `docType: "run"` — one `RunRecord` (`src/domain/observability.py`) per processed message:
  intent, selected agent, tool calls, tokens, estimated cost, latency, final status. Written
  once, by `ObservabilityService.record_run` (`src/observability/service.py`), from
  `apps/api/src/api/routes/chat.py` after `SupervisorOrchestrator.handle()` returns (or raises).
- `docType: "conversation_summary"` — one `ConversationSummary` per conversation, incrementally
  aggregated (run count, token/cost totals, primary domain, business outcome) as each run is
  recorded. This is what backs the dashboard's conversation table and KPI strip — it is read
  instead of the `conversations` container, so the dashboard never scans embedded message
  arrays (PBI-13-01 §6's "avoid expensive full-message scans").

Both document kinds share partition key **`/conversationId`** (not `/userId`): the conversation
detail view's two real reads — "every run for this conversation" and "this conversation's
summary" — become single-partition operations. The dashboard's cross-conversation list/KPI
queries are necessarily cross-partition in V1 (there is no partition key that groups "every
conversation across every user" together while `OBSERVABILITY_ACCESS_MODE=all_authenticated`
means any authenticated user can see all of them) — an accepted, documented V1 cost/scale
tradeoff, not an oversight; see the Consequences section.

`ObservabilityRepository` (`src/domain/observability_repository.py`) is a new Protocol,
structurally identical in spirit to `ConversationRepository` — `InMemoryObservabilityRepository`
(default, no Azure dependency) and `CosmosObservabilityRepository` (selected via
`OBSERVABILITY_STORE_PROVIDER=cosmos`), chosen by
`src/services/observability_store/factory.py`, mirroring
`src/services/conversation_store/factory.py` exactly. The `conversations` container's schema,
`ConversationRepository`'s existing methods, and the chat read/write path are **not** modified
by this feature at all.

## Alternatives considered

- **Option A (extend `Conversation` + one dedicated run container).** The initial framing
  (aggregate fields added directly onto the `Conversation` document). Rejected in favor of the
  design above during implementation: it still required a read-modify-write of the chat
  document for every run, and offered no benefit the separate `conversation_summary` document
  doesn't already provide, while carrying more regression risk to the existing chat path.
- **Option B (three containers: `conversations`, `messages`, `runs`).** Rejected —
  `PBI-13-01 §5` explicitly warns against automatically creating three containers, and this
  repository's chat experience does not need a separate `messages` container; only run-level
  telemetry was ever missing.
- **Cross-partition dashboard queries avoided via a per-day/per-shard partition key.** Considered
  and deferred — meaningfully more complexity for a V1, synthetic-data, academic-reference-scale
  system. Revisit if a future PBI's measured load justifies it.

## Consequences

- Positive: zero schema/behavioral change to the existing, working chat persistence path;
  conversation detail reads are single-partition; local development and the full test suite
  never require Cosmos DB (in-memory default, matching every other provider-selectable
  component in this repository).
- Negative / accepted: the dashboard's conversation list and summary KPIs run cross-partition
  Cosmos queries. At this project's synthetic-data, academic-reference scale this is
  acceptable; a real production rollout with meaningfully higher conversation volume should
  revisit this ADR (e.g. a per-day partition key, or a scheduled aggregation job) before
  relying on it at scale — a FinOps/scale follow-up, not a Phase 1 blocker.
- `OBSERVABILITY_STORE_PROVIDER` defaults to `in_memory` even in the DEV Bicep parameters
  (`ops/bicep/parameters/dev.bicepparam`) — the Cosmos-backed path is implemented and unit
  tested (with a mocked SDK client, same convention as `CosmosConversationRepository`'s own
  tests) but has not been validated against a real deployed Cosmos account. Flipping it to
  `cosmos` is a deliberate follow-up decision, not automatic.

## Review triggers

- Real conversation/run volume in a deployed environment approaches a scale where
  cross-partition dashboard queries measurably degrade (RU cost or latency) — revisit the
  partition-key strategy.
- `OBSERVABILITY_ACCESS_MODE` moves from `all_authenticated` to `roles` in production — revisit
  whether per-role data scoping (not just visibility) is also required.
- A future PBI needs Phase 2/3 quality signals (Operational Quality Score, repeated-question
  detection) to be queryable/filterable at the dashboard level, not just displayed per-run.

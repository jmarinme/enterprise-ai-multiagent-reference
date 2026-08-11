# ADR-0004: Conversation Store Selection — Azure Cosmos DB for NoSQL

## Status

Accepted — retroactively documented 2026-08-10 (PBI-10-02). This decision has been implemented
since Sprint 00/Sprint 04 (`src/services/conversation_store/cosmos.py`,
`ops/bicep/modules/cosmos-db.bicep`) and is codified in CLAUDE.md §4.3/§5. This ADR is the
first formal record of the *justification*, closing `docs/sprint_00/README.md` acceptance
criterion AC-06 ("Cosmos DB está justificado para conversaciones → ADR y documento de diseño"),
which was never satisfied by a dedicated document until now.

## Context

The platform needs a persistence layer for conversation history: per-turn messages, a rolling
summary, per-agent working state, sticky language, and (PBI-09-01) cross-agent global memory —
all namespaced under one synthetic `userId` (CLAUDE.md §4.3). This is operational/session data,
never core business truth (policies, claims, payments, commissions), which always comes from
Tools, never from the conversation store (CLAUDE.md principle #2).

## Problem

Which data store should back `ConversationRepository` (`src/domain/conversation_repository.py`),
and is that choice justified against real alternatives rather than assumed from the stack table
alone?

Requirements driving the choice:

- Partition-friendly access by a single key (`userId`) — CLAUDE.md §4.3 mandates
  `partition key: /userId` explicitly.
- Schema flexibility: `Conversation.metadata` is a free-form `dict[str, str]` that grows new
  keys over time (`claimsIntakeState`, `brokerInquiryState`, `commercialIntakeState`,
  `globalMemory`, `language` — see [ADR-0009](0009-conversation-memory-strategy.md)) without a
  migration for each new Agent or feature.
- Low operational overhead for an academic reference platform with synthetic, low-volume traffic
  — no dedicated database administration.
- Native Azure integration: Managed Identity authentication (CLAUDE.md §4.5), regional
  availability, and a serverless/consumption billing option matching the platform's
  conservative-cost posture (already applied to AI Search Free tier — see
  [ADR-0002](0002-vnet-private-endpoints-hardening.md)).
- A first-class async Python SDK, to fit the platform's async-I/O standard (CLAUDE.md §9 Python
  standards).

## Alternatives considered

- **Azure SQL / a relational store.** Rejected: conversation metadata's shape changes per Agent
  and per feature (new working-state keys are added by simply writing a new metadata key —
  see [ADR-0006](0006-provider-abstraction-pattern.md) and
  [ADR-0009](0009-conversation-memory-strategy.md)); a relational schema would require a
  migration for every such addition, working against CLAUDE.md's per-PBI incremental delivery
  model. A relational store's strengths (joins, multi-row transactions) are not needed here — the
  access pattern is always a single point-read or point-write of one conversation document.
- **Azure Table Storage.** Rejected: no native JSON document model (values would need manual
  serialization beyond what `Conversation.metadata`'s dict-of-strings already requires), weaker
  query flexibility (`list_conversations`' `ORDER BY c.createdAt DESC` — see
  `src/services/conversation_store/cosmos.py`), and no equivalent of Cosmos's
  `disableLocalAuth`/Managed-Identity-first data-plane security model
  ([ADR-0001](0001-networking-posture-and-vnet-deferral.md)).
- **Redis.** Rejected per CLAUDE.md §4.3 directly: "Redis is not part of Sprint 0. Add it only
  when an ADR and measured performance requirement justify it." No such requirement has arisen —
  conversation history needs durable persistence across restarts, not a cache.
- **A self-hosted document database (e.g., MongoDB on a VM/container).** Rejected: adds
  infrastructure operational burden (patching, backup, HA) with no compensating benefit over a
  managed PaaS option, and conflicts with CLAUDE.md §5's explicit exclusion of unmanaged
  database platforms unless a PBI requires one.

## Decision

Use **Azure Cosmos DB for NoSQL** as the sole conversation store, accessed exclusively through
the `ConversationRepository` Protocol (`src/domain/conversation_repository.py`).

- **Partition key**: `/userId`, per CLAUDE.md §4.3 — every point-read/point-write in
  `CosmosConversationRepository` (`get_conversation`, `append_message`) supplies it directly,
  avoiding a cross-partition fan-out query on the hot path.
- **Authentication**: `DefaultAzureCredential` (Managed Identity-compatible) only —
  `disableLocalAuth: true` in `ops/bicep/modules/cosmos-db.bicep`, matching ADR-0001's posture
  that Cosmos is the one data-plane service with key-based auth disabled unconditionally,
  regardless of network path.
- **Document shape**: one document per `Conversation` (`src/domain/conversation.py`),
  containing `userId`, `conversationId`, `messages`, `summary`, `status`, `currentAgent`,
  `metadata`, `feedback`, and timestamps — exactly the shape CLAUDE.md §4.3 specifies.
- **Serverless/consumption billing** in DEV — no dedicated provisioned throughput to manage for
  an academic-scale workload (`ops/bicep/modules/cosmos-db.bicep`).

## Consequences

- **Positive**: schema-flexible metadata growth (new Agent state keys, new global-memory fields)
  requires no store-level migration — only a new Pydantic model plus a new dict key.
  Managed-Identity-only access removes an entire class of credential-leak risk for this store.
  Partitioning by `userId` gives predictable, low-latency point reads/writes for the platform's
  actual access pattern (one user, one active conversation at a time).
- **Negative / accepted trade-off**: Cosmos DB for NoSQL has no native support for multi-document
  ACID transactions across partitions — not needed today (every write is scoped to one
  conversation document) but would need reconsideration if a future feature required atomically
  updating more than one conversation at once. Query flexibility is lower than a relational store
  for ad hoc cross-conversation analytics; none is required by any current PBI.
- **Retention/TTL is out of scope for this ADR.** `ops/bicep/modules/cosmos-db.bicep` enables the
  TTL capability at the container level but does not set an active retention period
  (`defaultTtl: -1`, i.e. off). Choosing a real retention value is a distinct, compliance-relevant
  decision (`docs/sprint_00/decisions.md`, PBI-00-05) and is explicitly **not** decided by this
  ADR — it requires its own follow-up ADR before any non-infinite retention value is set.

## Relationship with Conversation Repository

`ConversationRepository` (`src/domain/conversation_repository.py`) is the abstraction boundary:
it defines `create_conversation`, `get_conversation`, `list_conversations`, and `append_message`
as a Protocol, with two implementations selected by `ConversationStoreSettings.conversation_store_provider`
(`src/config/settings.py`) via `src/services/conversation_store/factory.py`:

- `InMemoryConversationRepository` (default, `in_memory`) — local development and every unit/
  integration/conversational test; zero Azure dependency.
- `CosmosConversationRepository` (`cosmos`) — this ADR's subject; the only implementation used
  in any deployed environment.

`append_message`'s contract — metadata is **replaced, never merged** — is a `ConversationRepository`
contract decision, not a Cosmos DB-specific behavior (the in-memory implementation honors the
same contract). This is the mechanism [ADR-0009](0009-conversation-memory-strategy.md) builds on
for per-agent state and global memory. This choice of Cosmos DB as the *backing technology* is
independent of, and does not constrain, the shape of what is stored in `metadata` — that is
governed entirely by [ADR-0006](0006-provider-abstraction-pattern.md)'s provider-swap boundary
and [ADR-0009](0009-conversation-memory-strategy.md)'s memory model.

## Review triggers

- Before setting a non-default (`-1`) TTL value on the `conversations` container — needs its own
  ADR per the accepted-risk note above.
- If a future requirement needs multi-document transactional consistency across conversations
  (not required by any current PBI).
- If conversation volume/access patterns change materially from "one user, one active
  conversation, occasional history list" (the pattern this ADR's partition-key choice assumes).

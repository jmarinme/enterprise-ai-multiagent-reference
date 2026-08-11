# ADR-0009: Conversation Memory Strategy — Metadata-Persisted State, Agent-Owned Global Memory

## Status

Accepted — retroactively documented 2026-08-10 (PBI-10-02). The per-agent working-state pattern
has been implemented since Sprint 01 (PBI-01-05/01-06); the global cross-agent memory extension
since Sprint 09 (PBI-09-01, `src/agents/shared/memory.py`). This ADR is the first formal record
covering both layers together as one coherent memory strategy.

## Context

CLAUDE.md §4.3 requires conversation history to include `userId`, `conversationId`, `messages`,
`summary`, `status`, `currentAgent`, `metadata`, `feedback`, and timestamps, persisted in Cosmos
DB ([ADR-0004](0004-conversation-store-selection.md)), and states directly that "core insurance
truth must never be stored in Cosmos DB as authoritative policy, claim, payment, or commission
data." Within that constraint, the platform still needs to remember, within one conversation:

- **Per-agent in-progress intake state** — which fields a Claims/Broker/Commercial flow has
  already collected, so a multi-turn intake does not restart from scratch each turn.
- **Cross-domain facts** — a policy number validated while handling a Claim should not be
  re-asked if the same caller later asks a Broker Services question in the same conversation.
- **Session-level preferences** — which language the caller has been using (sticky across turns).

`ConversationRepository.append_message` (`src/domain/conversation_repository.py`) imposes one
hard constraint on any strategy built on top of it: `Conversation.metadata` is `dict[str, str]`,
and is **replaced, never merged**, on every call — the caller must send its complete desired
metadata every turn, or a previously-stored key is silently lost.

## Decision

### Conversation state model: everything lives in `Conversation.metadata`, never a new store

No dedicated session store, cache, or additional database was introduced. Every piece of
in-conversation memory — per-agent state, global memory, language — is a JSON-serialized value
under its own string key inside the same `metadata: dict[str, str]` field CLAUDE.md §4.3 already
specifies, persisted through the same `ConversationRepository` every other conversation write
uses ([ADR-0004](0004-conversation-store-selection.md)).

### Agent-local memory: one metadata key per multi-turn Agent

`src/agents/shared/state_persistence.py` provides the shared pattern (extracted in PBI-01-05/
01-06 after `ClaimsAgent` and `BrokerAgent` had each implemented it independently):

- `load_agent_state(metadata, key, state_type)` — deserializes a Pydantic `BaseModel` from
  `metadata[key]`, or returns a fresh, empty instance if the key is absent or the stored value is
  corrupt/incompatible ("a bad stored snapshot must never crash the conversation — it just starts
  the flow over").
- Three keys are currently in use, one per multi-turn Agent
  (`KNOWN_AGENT_STATE_KEYS` in the same module): `claimsIntakeState`, `brokerInquiryState`,
  `commercialIntakeState`.
- `carry_forward_other_agent_state(metadata, own_key)` — because metadata is replaced wholesale
  each turn, every Agent must explicitly re-include every *other* Agent's state key, unparsed and
  unmodified, in its own response metadata, or a cross-domain handoff (e.g., Claims → Broker)
  would silently destroy whichever other Agent's in-progress intake was under way. Each Agent
  still only ever reads and acts on its own key — a carried-forward entry is inert baggage until
  that Agent is addressed again.

### Global memory: Agent-owned, not Supervisor-owned

`src/agents/shared/memory.py` (PBI-09-01) introduces `ConversationMemory`, a single structured
value object (customer name, broker id/name, policy number, claim number, business name, incident
date/type/location, coverage, current/previous intent, a conversation summary) shared across all
three domain Agents under one metadata key, `GLOBAL_MEMORY_METADATA_KEY = "globalMemory"`.

- **Ownership**: each Agent — not the Supervisor — loads (`load_memory`), reads relevant fields to
  pre-fill its own state (skipping a question already answered by a fact learned in another
  domain), updates (`update_memory`) with anything newly learned this turn, and re-emits
  (`save_memory`) the result in its own `AgentResponse.metadata` every turn. `SupervisorOrchestrator`
  never inspects or mutates `ConversationMemory` directly — it only persists whatever metadata the
  acting Agent returns, via the same `append_message` call it already makes for every other
  metadata key.
- **Non-destructive updates**: `update_memory` never overwrites an already-known value with an
  empty one (`None`, `""`, or `[]`) — a later turn that simply didn't mention a field must not
  erase what an earlier turn already established.
- **Intent rotation**: `update_memory` rotates `current_intent` → `previous_intent` whenever the
  acting Agent differs from the last one that touched memory, giving a reliable signal of genuine
  domain switching (Claims → Broker → Commercial) distinct from repeated turns with the same
  Agent.
- **Not core business truth**: the module's own docstring states this directly — `ConversationMemory`
  is "a cache of facts already confirmed by a Tool or already given by the caller, used only to
  avoid a redundant question or a redundant Tool call. Every business action still goes through
  the same approved Tools it always did (CLAUDE.md §3)." A remembered policy number is never used
  in place of a fresh `policy_lookup`/`validate_policy_status` Tool call when a business decision
  actually depends on that policy's current state — memory only changes *whether* a field still
  needs asking, never *how* it is validated. This keeps the memory layer fully compliant with
  [ADR-0007](0007-ai-governance-boundary.md)'s boundary (business facts come from Tools, not from
  stored/remembered LLM-adjacent state).

### Metadata persistence and state synchronization

Every Agent follows the same per-turn cycle:

1. Load its own working state (`load_agent_state`) and the shared `ConversationMemory`
   (`load_memory`) from the incoming `metadata`.
2. Pre-fill any of its own state fields the global memory already has an answer for (skipping a
   redundant question).
3. Process the turn (extract new facts from the message, call Tools, advance its state machine).
4. Update `ConversationMemory` with anything newly learned or confirmed this turn
   (`update_memory`).
5. Return `AgentResponse.metadata` containing: its own state key (`save`d), the updated
   `globalMemory` key (`save_memory`), the language key (unchanged if not newly detected), and
   every other Agent's carried-forward state key (`carry_forward_other_agent_state`).

`SupervisorOrchestrator` treats this returned `metadata` dict as the complete, authoritative
metadata for the conversation going forward and persists it verbatim via
`ConversationRepository.append_message` — synchronization is achieved by every Agent always
re-sending the full picture, never by any partial-update or locking mechanism, which the
underlying store's replace-never-merge contract ([ADR-0004](0004-conversation-store-selection.md))
would not support anyway.

## How this enables seamless transitions between Claims, Broker Services, and Commercial Intake

Concretely, in a conversation that starts with a Claims flow, switches to a Broker Services
question, and returns to Claims:

1. **Claims** validates a policy number via `policy_lookup`, stores it in its own
   `claimsIntakeState.policy_number` (already-validated, protected from being overwritten by a
   later partial extraction) and also writes it into `ConversationMemory.policy_number`.
2. The caller asks about commissions. `RuleBasedIntentResolver` routes to Broker
   ([ADR-0007](0007-ai-governance-boundary.md)). `BrokerAgent` loads `ConversationMemory`, finds
   `policy_number` already known, and does not re-ask for it if its own flow needs one — while
   `carry_forward_other_agent_state` ensures Claims' own `claimsIntakeState` (still
   mid-conversation, not yet confirmed/registered) survives untouched in metadata even though
   Broker is the Agent answering this turn.
3. The caller returns to Claims ("ahora quiero continuar con mi siniestro"). `ClaimsAgent` reads
   its own `claimsIntakeState` back from metadata — exactly where it left off — never having lost
   state to the intervening Broker turn.

This is the direct mechanism behind CLAUDE.md §4.3's context-management requirement and the
Supervisor's stated responsibility to "maintain context" across a routed, multi-agent
conversation — implemented without a dedicated session-affinity service, a shared mutable session
object, or any store beyond the one `ConversationRepository` already provides.

## Alternatives considered

- **Supervisor-owned global memory** (Supervisor reads/writes `ConversationMemory` directly,
  independent of which Agent is acting). Rejected (`docs/sprint_09/decisions.md`, D-01): this
  would require the Supervisor to understand every Agent's fact vocabulary (what a "policy
  number" or "broker id" means to each domain), coupling a component CLAUDE.md §4.1 defines as
  routing-only ("It does not execute business logic") to domain-specific knowledge. Agent-owned
  memory keeps this coupling at zero — the Supervisor persists whatever metadata it is given
  without needing to interpret any of it.
- **A dedicated session/memory store separate from `Conversation.metadata`** (e.g., Redis, a
  second Cosmos container). Rejected per CLAUDE.md §4.3's explicit Redis deferral, and because
  the existing `ConversationRepository`/Cosmos DB combination
  ([ADR-0004](0004-conversation-store-selection.md)) already satisfies the access pattern (single
  point-read/write per conversation) without adding a second store to keep consistent with the
  first.
- **Merging metadata updates instead of replacing wholesale.** Rejected — not actually available:
  `ConversationRepository.append_message`'s contract is replace-only by design (its own docstring:
  "the Agent always sends its complete current state, not a partial patch"), chosen originally to
  avoid distributed-merge ambiguity (which Agent's concurrent update wins) in a single-writer-per-
  turn system where exactly one Agent ever handles a given turn.
- **Storing core business facts (validated policy status, confirmed claim outcome) in
  `ConversationMemory` as the source of truth for later reuse.** Rejected: this would violate
  CLAUDE.md §4.3 and [ADR-0007](0007-ai-governance-boundary.md) directly — memory caches *that a
  fact was already established*, never substitutes for re-validating it through a Tool when a
  business decision depends on its current state.

## Consequences

- Positive: cross-domain handoffs (Claims ↔ Broker ↔ Commercial) preserve both the leaving
  Agent's in-progress state and the shared facts every Agent can draw on, with zero additional
  infrastructure beyond the existing Cosmos-backed `ConversationRepository`.
- Positive: a corrupt or missing metadata key never crashes a conversation — every load path
  (`load_agent_state`, `load_memory`) fails safe to a fresh, empty value.
- Negative / accepted trade-off: every Agent must remember to carry forward every other Agent's
  state key and re-emit the global memory key on every turn — a real discipline the pattern
  depends on; omitting it silently loses state on the very next turn (this exact class of bug was
  found and fixed for the Claims policy-number field during PBI-09-01A's functional-fix work,
  though the general carry-forward mechanism itself was already in place since PBI-05-01).
- Negative / accepted trade-off: `Conversation.metadata` grows one JSON-serialized key per
  concern (three agent-state keys, one global-memory key, one language key today); each is a
  small, bounded structure, but there is no enforced upper bound on `ConversationMemory`'s own
  growth if more fields are added in the future — acceptable at the platform's current scope,
  worth revisiting only if metadata payload size becomes materially significant.

## Relationship with other ADRs

- [ADR-0004](0004-conversation-store-selection.md) — the storage technology and the
  replace-never-merge contract this entire strategy is built on top of.
- [ADR-0006](0006-provider-abstraction-pattern.md) — `ConversationRepository`'s own
  provider-swap boundary is independent of, and unaffected by, how its `metadata` field is
  structured internally.
- [ADR-0007](0007-ai-governance-boundary.md) — the explicit boundary that memory is a caching/
  convenience layer, never a substitute for Tool-sourced business truth.

## Review triggers

- Before adding a fourth multi-turn Agent — extend `KNOWN_AGENT_STATE_KEYS` and follow the same
  load/carry-forward/save cycle documented here.
- If `Conversation.metadata`'s total serialized size becomes a measured concern — consider
  whether every `ConversationMemory` field is still pulling its weight, or whether summarization
  (already used for message history, `src/agents/shared/summary.py`) should extend to memory too.
- If a future requirement needs memory to persist *across* conversations for the same user (today
  scoped to one `conversationId` only) — that is a materially different requirement needing its
  own ADR, not an extension of this one.

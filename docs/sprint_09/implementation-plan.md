# Sprint 09 Implementation Plan

## PBI-09-01 — Conversation Intelligence & Multi-domain Orchestration

### Design decision: where does global memory live?

`Conversation.metadata` (and every layer built on it — `ConversationContext.metadata`,
`AgentResponse.metadata`) is `dict[str, str]`, and `ConversationRepository.append_message`
**replaces**, never merges, stored metadata each turn. Every existing per-agent working-state
model (`claimsIntakeState`, `brokerInquiryState`, `commercialIntakeState`) and `language` already
solve this the same way: each Agent explicitly loads its own key from `context.metadata`,
computes its update, and re-emits every key it wants to survive into its own
`AgentResponse.metadata` every turn (`carry_forward_other_agent_state` copies the *other* two
agents' raw state forward unread).

Two designs were possible for global memory:

1. **Supervisor-owned**: `SupervisorOrchestrator.handle()` loads/updates/persists a shared memory
   object itself, around each `agent.handle()` call, independent of what any Agent does.
2. **Agent-owned, shared key** (chosen): a new `src/agents/shared/memory.py` module — the same
   shape as `state_persistence.py` — with a well-known metadata key (`globalMemory`). Each Agent
   loads it at the top of `handle()`, pre-fills its own state from it (slot filling), and after
   running its own workflow, folds newly-learned facts back in and re-emits it in its own
   `AgentResponse.metadata`, exactly like `language`.

(2) was chosen because it requires zero change to `SupervisorOrchestrator`, `ConversationContext`,
or `AgentResponse` (CLAUDE.md's own "do not redesign architecture" instruction for this PBI), and
because it is consistent with the codebase's existing, already-tested explicit-metadata-threading
convention — a hidden Supervisor-level side channel would be a new pattern, not a reuse of one.

### Files created

| File | Purpose |
|---|---|
| `src/agents/shared/memory.py` | `ConversationMemory` (15-field shared model), `load_memory`/`update_memory`/`save_memory`, `GLOBAL_MEMORY_METADATA_KEY`. |
| `src/agents/shared/summary.py` | `build_progress_summary()` — the "Hasta ahora tengo: ✔ ..." checkmark recap. |
| `tests/unit/agents/shared/test_memory.py` | Unit tests for the memory model. |
| `tests/unit/agents/shared/test_summary.py` | Unit tests for the summary formatter. |
| `tests/conversational/test_global_memory_and_multi_domain_orchestration.py` | API-level acceptance tests (see `validation.md`). |
| `docs/sprint_09/*` | This sprint's mandatory documentation. |

### Files modified

| File | Change |
|---|---|
| `src/agents/shared/nlu.py` | `resolve_relative_date` now also resolves "la semana pasada"/"last week" (requirement 4). |
| `src/agents/claims/extraction.py` | `_LOSS_TYPE_KEYWORDS` gained `"llov"`/`"lluvia"` → `"weather"` (requirement 4's own example). |
| `src/agents/claims_agent.py` | Loads/pre-fills/updates/re-emits global memory; injects the progress-summary prefix while still collecting core fields. |
| `src/agents/broker_agent.py` | Same pattern — additionally skips a redundant `broker_lookup` Tool call when `broker_id` is already known from memory (requirement 10). |
| `src/agents/commercial_intake_agent.py` | Same pattern — reuses `business_name`/`customer_name`. |
| `src/agents/broker/state.py`, `src/agents/broker/workflow.py` | Reworded 3 user-facing "correduría" strings to "broker" (requirement 8). |

### Why pre-fill is gated on `state.status == <Status>.NEW`

Each Agent's own decline/correction flow (e.g. `ClaimsAgent`'s `_handle_confirming` clearing
incident fields back to `None` so the caller can correct them) must never be silently undone by
memory re-filling the same field with the stale value on the very next turn. Gating the
memory-prefill step to only run when the Agent's own state is still fresh (`NEW` — true only on
that Agent's genuine first turn in the conversation, since the state machine always advances past
`NEW` within the same turn it starts) means every later turn is governed exclusively by that
Agent's own extraction/decline logic, with memory read once and never re-applied over a
caller-in-progress correction.

### Slot-filling order implemented (requirement 2)

Each Agent's `handle()` now follows: **global memory → own workflow's existing tool-backed
resolution (customer discovery, broker-name lookup, policy validation) → ask the user** — matching
the specified priority order exactly, since the existing state machines already implement
"tool output before asking" and this PBI only inserts the memory check ahead of that.

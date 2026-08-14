# Sprint 14 — Decisions and Deviations

Every deviation from the literal driving-PBI framing, disclosed here per CLAUDE.md §12.

## PBI-14-03

1. **Supervisor kept 100% deterministic, not "LLM-informed" routing.** The driving PBI's section
   5 could be read as asking semantic intent to *inform* routing. The only reusable LLM call
   happens inside a specialist agent, after the Supervisor has already picked it — using it to
   re-route would need either a new pre-routing LLM call (violates the zero-new-calls target) or
   a materially larger Supervisor redesign. Resolved by strengthening
   `RuleBasedIntentResolver` with a genuinely deterministic compound-pattern rule instead — see
   ADR-0013's "Why the Supervisor was NOT made LLM-informed" for the full rationale. This is a
   stricter interpretation than the letter of the request, chosen for lower regression risk and
   consistency with ADR-0011's existing boundary.

2. **`AgentResponse.routing_diagnostics` added as a new, separate field — not reused via
   `metadata`.** First attempt wrote routing telemetry into `AgentResponse.metadata` (the
   existing "technical, never user-visible" channel each Agent's `diagnostics` key already
   uses). This broke two existing tests
   (`test_handle_persists_agent_response_metadata_on_a_new_conversation`,
   `...updates_persisted_metadata...`) because `metadata` round-trips into the persisted
   `Conversation` document via `_persist_turn` — routing diagnostics have no long-term value to
   chat history and would have bloated every stored conversation forever. Corrected to a
   dedicated `routing_diagnostics` field, read only by the observability call site
   (`apps/api/src/api/routes/chat.py`) and never passed to `_persist_turn`.

3. **`MIN_CONFIDENCE_TO_APPLY = 0.5`** (`src.agents.shared.semantic_merge`) is a judgment call,
   not a value specified by the driving PBI. Chosen as the natural midpoint threshold; a future
   PBI with real measured precision/recall data should revisit it explicitly rather than treat
   0.5 as validated.

4. **`industry`/`location`/`insured_value` are never passed to `LeadRegistrationTool`.** The
   Tool's `LeadRegistrationInput` schema has no such fields, and changing a Tool's contract is
   out of this PBI's scope (CLAUDE.md's Tool-contract versioning discipline). These three fields
   are stored on `CommercialIntakeState`, shown back to the caller in the pre-registration
   confirmation summary for correction, and available for future observability/Tool work — never
   silently discarded, never silently smuggled into a Tool call the contract doesn't support.

5. **`"confirmed"` (Claims) and `"wants_payment_request"` (Broker) removed from each
   extraction.py's generic `_YES_NO_FIELDS` first-word check.** Both fields now resolve
   exclusively through the shared `resolve_confirmation` module (called from each `workflow.py`),
   which understands a materially wider vocabulary than the old narrow `_YES_WORDS`/`_NO_WORDS`
   sets. Two now-redundant extraction-level tests
   (`test_yes_no_answer_is_only_interpreted_for_the_last_asked_yes_no_field`,
   `test_no_answer_sets_wants_payment_request_false` in `test_broker_extraction.py`) were removed
   because the equivalent behavior is already covered at the workflow level
   (`test_confirming_payment_request_registers_it_with_a_synthetic_reference`,
   `test_declining_payment_request_completes_without_registering_one`) — not a coverage
   reduction, a relocation to where the behavior now actually lives.

6. **Cosmos KPI-aggregation cost-nullability fix (`src/services/observability_store/cosmos.py`)
   is unverified against a real Cosmos DB.** `CosmosObservabilityRepository` is explicitly never
   exercised by the test suite against real Azure (same documented pattern as
   `AzureOpenAIProvider` — `MockLLMProvider`/`InMemoryObservabilityRepository` are what tests
   actually exercise). The fix (an added `COUNT(c.totalEstimatedCostUsd) AS costKnownCount`
   alongside the existing `SUM`, compared against `conversationCount`) is written correctly per
   Cosmos SQL's documented aggregate-function semantics, but — consistent with this repo's
   existing disclosed limitation for that file — was not runtime-verified against a live Cosmos
   instance. The equivalent `InMemoryObservabilityRepository` logic IS test-verified (see
   `tests/unit/services/test_observability_store_in_memory.py`'s new cost tests) and shares the
   same "once Unavailable, stays Unavailable" contract.

7. **Per-field provenance telemetry, repeated-question/confirmation-retry counters, and
   `RunRecord` schema additions beyond `intent_confidence`/`routing_reason` were not built.**
   The driving PBI explicitly scoped observability as secondary and warned against "another
   observability redesign." `intent_confidence`, `routing_reason`, `routing_source`, and the
   `$0.0000` cost fix were judged the practically achievable, genuinely real signals within that
   constraint; the rest remain honestly absent rather than fabricated or half-built.

8. **Regression test scenarios use `MockLLMProvider.structured_response_sequence` (new
   capability), not the exact literal N-turn dialogue quoted in the driving PBI.** The PBI's
   illustrative dialogues (e.g. Claims' 5-message exchange ending in "sip") are shorter than the
   number of turns the still-unchanged required-field checklist actually needs to reach
   registration (the PBI's own "ReAct must remain / do not create another orchestration engine"
   constraint means the field checklist itself was not shortened, only the *extraction
   richness* per turn). Each regression test drives the full number of turns actually required,
   using the PBI's own critical messages verbatim at the turns where they matter (the compound
   narrative message, the "sip"/"va" confirmations, the incendio/fábrica message), and asserts
   the specific documented defect is fixed rather than asserting an exact turn count that was
   never itself a stated requirement.

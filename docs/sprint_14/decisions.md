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

## PBI-14-04

Also disclosed per CLAUDE.md §12; note item 1 in the PBI-14-03 list above (Supervisor kept 100%
deterministic) is the resolution PBI-14-04 revisits — see its own retrospective addendum in
`README.md` for why that earlier, narrower reading turned out to leave the actual reported
defect unfixed, and what changed instead (the Supervisor is still deterministic; what moved was
WHEN the existing semantic call runs, not WHETHER the Supervisor "reasons").

1. **Malformed structured-output JSON is treated as a semantic-call failure (routes via
   `RuleBasedIntentResolver`), even though `interpret_semantics`'s own diagnostic string still
   contains `"[llm=...]"` in that case.** Discovered while writing
   `test_malformed_structured_output_falls_back_to_rule_based_resolver`: `interpret_semantics`
   builds its `"[llm=...]"` diagnostic suffix BEFORE attempting to parse the completion, so a
   parse failure (caught, degrading to the safe-empty `TurnInterpretation`) still carries that
   suffix — the diagnostic string alone cannot distinguish "genuinely classified as unknown" from
   "the response was unparseable." Fixed by also checking whether the returned
   `TurnInterpretation` exactly matches the safe-empty sentinel shape
   (`src.supervisor.semantic_routing._is_empty_sentinel`) before trusting `"[llm=...]"` as proof
   of a real classification. `interpret_semantics`'s own existing diagnostic contract was left
   unchanged (a PBI-14-03 test already asserts `"[llm=...]"` appears even on malformed JSON) —
   the fix lives entirely in the NEW routing-decision code, not the shared, already-tested
   interpreter.

2. **`SupervisorConfig` gained two new fields (`semantic_routing_high_confidence`/
   `semantic_routing_low_confidence`) rather than a separate injected config object.** Keeps the
   existing "everything flows through one `SupervisorConfig`, no globals" pattern intact;
   `SupervisorOrchestrator.__init__` constructs the internal `SemanticRoutingConfig` dataclass
   `src.supervisor.semantic_routing.resolve_turn` actually consumes from these two fields, so
   callers configuring the Supervisor never need to know about the internal dataclass split.

3. **The `Agent` Protocol's two new parameters default to `None`/`""` rather than being
   required.** A required parameter would have forced every existing direct-Agent-call test
   (dozens, across PBI-01-05 through PBI-14-03) to change just to keep compiling/type-checking,
   for a value most of them have no reason to construct. The optional-with-safe-fallback design
   (mirrored from `on_react_event`'s own precedent, PBI-13-01) let all ~800 pre-existing tests
   pass completely unmodified — verified, not assumed, by running the full suite after every
   implementation step.

4. **Real Azure OpenAI classification quality for the PBI's own listed paraphrase test cases
   (sections 11-14) was not verified against a live Azure OpenAI deployment.** This sandbox has
   `LLM_PROVIDER=mock` configured locally and no Azure OpenAI credentials available — the same
   disclosed, pre-existing limitation `AzureOpenAIProvider` has always carried in this repo (it
   is "never exercised by the test suite against real Azure," per its own module docstring,
   unchanged since before this PBI). The domain-paraphrase tests instead verify the DOWNSTREAM
   deterministic routing logic correctly converts a given classification into the correct Agent
   selection — the actual architectural bug this PBI fixes — while the separate question of
   whether a real deployed model classifies these exact phrasings correctly is a live-deployment
   validation concern, not something a local sandbox without Azure credentials can answer. See
   `validation.md`'s "Not run (and why)" section.

5. **`FallbackAgent`'s clarification templates cover exactly the three unordered domain pairs
   (Claims/Broker, Claims/Commercial, Broker/Commercial) plus one generic fallback, not a
   template per every possible `alternative_intents` combination.** The shared prompt instructs
   the model to return at most two runner-up intents, and there are only three possible domains
   to pair against the primary one — three specific templates plus one generic "I need a bit
   more detail" fallback (used when `alternative_intents` is empty, more than one candidate pair
   is present, or a candidate is `unknown`) covers every reachable case without over-building a
   templating system for combinations that cannot occur.

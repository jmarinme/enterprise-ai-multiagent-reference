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

## PBI-14-05 (`azure-pipelines.yml` delivery consistency — unrelated theme, see README.md)

1. **The `apps/web`-changed diff check was kept, not deleted, inside `ContainerBuildAndPush`
   (renamed output `webChanged` -> `webChangedInfoOnly`) — it just no longer gates anything.**
   The driving task said "remove or bypass" the optimization for the main path; bypassing
   (computing the same signal for `DeploymentSummary`'s informational "did apps/web literally
   change" line, but never branching on it for build/push/deploy) was chosen over outright
   deletion because the signal itself is harmless and mildly useful evidence in the summary
   artifact — the actual defect was ONLY that it gated real delivery, not that the detection
   existed. The variable was explicitly renamed (not just re-documented) specifically so a
   future edit cannot accidentally re-wire the old `webChanged` name back into a conditional by
   muscle memory — the new name states in the identifier itself that it must never gate
   anything.

2. **A new Smoke Tests step (deployed Web image-tag verification) was added rather than only
   relying on `DeploymentSummary`'s own tag-consistency check.** The driving task's own
   validation list (#3, "API and Web use the same BuildId + commit-SHA image tag") and its
   explicit "do not weaken smoke tests" / "verify that both match the current pipeline imageTag"
   instructions both point to Smoke Tests as the actual PASS/FAIL gate — `DeploymentSummary`
   only publishes evidence and does not fail the pipeline on a mismatch by itself (it runs after
   Smoke Tests and depends on it having succeeded). Putting the real gate in Smoke Tests (which
   already fails the pipeline via `exit 1` + `set -e`) means a future Web-deploy regression is
   caught before the pipeline reports success, not merely noted afterward.

3. **This sandbox cannot execute a real Azure DevOps pipeline run.** Validation for this PBI is
   therefore: (a) YAML syntax parsed successfully (`python -c "import yaml; yaml.safe_load(...)"`,
   11 stages enumerated, matching the pre-change stage count exactly); (b) a line-by-line
   structural diff review confirming every hunk falls strictly within
   `ContainerBuildAndPush`/`DeployDev`/`SmokeTests`/`DeploymentSummary` (main-deploy-only
   stages) and never touches `ContainerBuildValidation`, `BackendQuality`, `FrontendQuality`,
   `SecurityScan`, `InfrastructureValidation`, or `InfrastructureDeploy`; (c) an explicit
   citation, per required-validation item, of exactly which lines implement it — see
   `validation.md`. This is disclosed as a real, unavoidable limitation, not silently assumed
   away — an actual pipeline run against Azure DevOps remains the only way to observe this
   change's real-world behavior end to end.

## PBI-14-07 (structured routing telemetry fix — unrelated theme, see README.md)

1. **Root cause confirmed exactly as diagnosed before implementation began (per the driving
   task's own section 1 "STOP if incorrect" gate) — no scope change needed.** Reading
   `apps/api/src/observability/logging.py`'s `JsonFormatter.format()` showed it builds its
   output `payload` dict from five fixed keys only and never inspects any `extra`-set
   `LogRecord` attribute. Confirmed live: `src.supervisor.orchestrator`'s pre-existing
   `supervisor_turn_latency` event (already setting `routingSource`/`conversationId`/`agent`/
   timing fields via `extra=`) produced real Container App log lines containing only
   `timestamp`/`level`/`logger`/`message`/`correlationId` — proving the fields were being lost
   in production, not merely in theory.

2. **`RoutingDecision` gained `semantic_call_succeeded`/`semantic_error_category`, set explicitly
   at all 7 of `resolve_turn`'s return sites — never inferred afterward from
   `routing_source`/`routing_reason`.** `routing_source=ROUTING_SOURCE_DETERMINISTIC_FALLBACK`
   is genuinely ambiguous on its own: it fires both when the semantic call itself failed
   (`routing_reason="semantic_service_unavailable"`) AND when it succeeded but returned low
   confidence (`routing_reason="low_semantic_confidence"`) — `test_low_confidence_falls_back_to_
   keyword_resolver` in `tests/unit/supervisor/test_semantic_routing.py` is the concrete
   regression this distinction protects: without it, a low-confidence-but-real classification
   would be indistinguishable in logs from a genuine Azure OpenAI outage.

3. **`semantic_error_category` normalization is coarser than the driving task's own example list
   (`provider_authentication_error`/`provider_timeout`/... collapse into one `provider_error`).**
   Achieving that finer granularity would require `src.agents.shared.semantic_interpreter.
   interpret_semantics` to propagate the specific caught exception type instead of collapsing
   every `LLMError` subtype into one generic swallow — but `interpret_semantics` is a shared
   function with 4 call sites (this module plus each specialist Agent's own backward-compat
   fallback path), and widening its return contract for all of them was judged to cross into the
   "architecture redesign" this PBI's own section 22 says to STOP for, given the driving task's
   explicit "keep this surgical... a small number of application modules" scope. Only 3 safely
   distinguishable categories were implemented (`prompt_error`/`provider_error`/
   `schema_validation_error`), derived entirely from the diagnostic string `interpret_semantics`
   already returns — zero changes to that shared function or its 4 call sites.

4. **The allowlist (`_ALLOWED_EXTRA_FIELDS`) covers exactly the routing-telemetry fields the
   driving task's own "conceptual allowlist" listed (translated to this repo's existing
   camelCase convention for this exact field family — `_routing_diagnostics_payload`,
   `chat.py`), not every pre-existing `extra=` call site's fields.** Several OTHER call sites
   (`orchestrator.py`'s own `agent`/`contextLoadMs`/`semanticMs`/`agentHandleMs`/`persistMs`/
   `totalMs`; `health.py`'s `dependency`; `src/core/tool_provider/azure_function.py` and
   `src/core/workflow_provider/durable.py`'s `tool_name`/`error`/snake_case `correlation_id`)
   were ALSO silently dropped by the same defect and remain so after this fix — deliberately, to
   keep the change surgical per the driving task's own file-scope instruction. Restoring those is
   a natural, low-risk follow-up (the allowlist only needs new entries, no formatter redesign)
   but was not bundled into this PBI.

5. **`correlationId`/`correlation_id` are deliberately excluded from the allowlist.** The
   correlation id in every log line always comes from `correlation_id_ctx_var` (set once per
   request by `CorrelationIdMiddleware`) via the pre-existing `CorrelationIdFilter` — never from
   a caller-supplied `extra` value. This preserves a real security/consistency property already
   implicit in the original (broken) formatter: no individual log call site can spoof or drift
   from the one authoritative, request-scoped correlation id. Tested explicitly
   (`test_correlation_id_always_comes_from_context_var_not_caller_supplied_extra`).

6. **The new log event is emitted from `apps/api/src/api/routes/chat.py`, not
   `src.supervisor.orchestrator` or `src.supervisor.semantic_routing`.** `chat.py`'s own
   docstring states it "contains no business logic" — but emitting an already-computed,
   already-authoritative routing decision as a log line is observability, not business logic
   (the same reasoning `src.observability.service.ObservabilityService`'s own docstring already
   uses: "Instrumented at one architectural boundary — the API layer, after
   SupervisorOrchestrator.handle() returns"). Reuses the exact local variables already unpacked
   for the pre-existing `observability.record_run()` call — no new computation, no second pass
   over `routing_diagnostics`.

7. **`_routing_diagnostics_payload` (orchestrator.py) gained two new string-keyed entries
   (`semanticCallSucceeded`, `semanticErrorCategory`) rather than widening
   `AgentResponse.routing_diagnostics`'s type from `dict[str, str]` to `dict[str, str | None]`.**
   `semanticErrorCategory` is represented as `""` (never Python `None`) in this dict specifically
   to avoid touching `src/supervisor/models.py`'s field type — `chat.py` maps `"" -> None` when
   building the log event's JSON. A one-line, additive, purely-representational choice, not a
   behavior change.

8. **The existing production regression test
   (`tests/unit/supervisor/test_pbi_14_04_production_regression.py`) was left completely
   untouched, per the driving task's explicit instruction.** New assertions for the two fields
   above were instead added to the existing, more granular `tests/unit/supervisor/
   test_semantic_routing.py` (which already had one test per routing-decision branch) and to two
   new dedicated files (`tests/unit/api/test_json_formatter.py`,
   `tests/unit/api/test_semantic_routing_log_events.py`) — the regression test continues to
   validate routing behavior independently of the logging change, exactly as required.

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

## PBI-14-06 (deployment verification + build/version visibility — unrelated theme, see README.md)

Unlike PBI-14-05, this session had genuine, authenticated `az` CLI access (subscription Owner on
the real DEV subscription) — a capability not available/exercised in earlier PBIs of this sprint.
This let section 1's deployment-state evidence and part of section 8's live diagnostic be
answered with real Azure queries rather than the "no Azure credentials available" disclaimer
PBI-14-04/14-05 both carried. See `validation.md` for the full evidence.

1. **`app_version` is a hand-maintained `Settings`/Dockerfile-`ARG` default (`"14.6.0"`), never
   sourced from CI — only `build_number`/`commit_sha` are.** The driving task explicitly forbids
   hardcoding the commit SHA but treats the human-readable app version as a separate, legitimately
   maintained identifier (its own example: `"App Version: 14.06"` alongside a CI-sourced build
   number). `apps/api/pyproject.toml`/root `pyproject.toml`/`apps/web/package.json` all still say
   `"0.1.0"` and were deliberately left untouched — nothing in the runtime code path reads any of
   them today (confirmed by grep), so wiring `app_version` to parse one of them at startup would
   add real complexity (a `tomllib`/`package.json` read) to synchronize with a value nothing else
   depends on, not remove one — the opposite of "do not introduce another version-management
   system." `app_version` in `Settings`/`env.ts` is the one new, single source of truth this PBI
   introduces; the three pre-existing, disconnected `"0.1.0"` fields are an unrelated, pre-existing
   concern out of this PBI's scope to unify.

2. **Extended the existing `GET /version` (already returning `name`/`version`/`environment`)
   rather than creating a new endpoint or extending `/health`.** The driving task explicitly
   offered this option ("extend an existing health/readiness endpoint if that is architecturally
   cleaner"). `/health` is a narrow liveness probe (`{"status": "ok"}`, no dependencies, used by
   orchestrators); `/version` already exists, is already unauthenticated, and already returns
   exactly the kind of identity/build metadata this PBI adds to — appending four new keys to its
   existing response is the smaller, more architecturally consistent change, and the frontend
   already fetches it once via `useApiStatus()` with zero new network calls needed.

3. **Web/API version-drift detection is a single equality check inside `Sidebar.tsx`, not a new
   service or polling loop.** Reuses the `VersionResponse` `useApiStatus()` already fetches once
   on mount; compares `apiVersionInfo.app_version`/`commit_sha` against the Web bundle's own
   build-time `webAppVersion`/`webCommitSha` constants (`apps/web/src/config/env.ts`). Drift is
   only flagged when both sides report a real pipeline-injected commit (never when either is the
   local-dev placeholder `"unknown"`), so a developer running `docker-compose` locally never sees
   a spurious drift warning. No new runtime complexity per the driving task's own section 5
   constraint.

4. **Two new Smoke Tests (3/7, 4/7) verify the DEPLOYED, RUNNING application's build identity,
   not just its image tag.** Smoke Tests 1/7-2/7 (pre-existing, PBI-14-05) already verify the
   Container App's `properties.template.containers[0].image` field matches this run's
   `$(imageTag)` — proof the *reference* was updated. 3/7 calls the live `GET /version` and
   asserts `commit_sha`/`build_number` equal `$(Build.SourceVersion)`/`$(Build.BuildNumber)`; 4/7
   fetches the live Web app's served JS bundle and asserts the same commit SHA literal appears in
   it. This closes a real, distinct failure mode the driving task called out directly ("a
   deployment must not be considered successful if Azure is still serving an older application
   build") — an image-reference update that doesn't actually result in new content being served
   (a stuck/cached revision, a container that didn't restart) would pass 1/7-2/7 but fail 3/7-4/7.

5. **Section 8's live diagnostic was run for real, against the real DEV Azure OpenAI resource,
   using this repo's own unmodified `resolve_turn`/`AzureOpenAIProvider` code — but could not be
   completed as the deployed application's own identity.** Two independent, disclosed auth
   boundaries block it, neither touched or worked around: (a) a delegated Entra ID user token for
   this API's own `access_as_user` scope requires interactive browser consent, unobtainable
   non-interactively (`az account get-access-token` fails with `AADSTS65001 consent_required`) —
   the same limitation already disclosed under PBI-14-04's decisions item 4; (b) this session's
   own Azure CLI identity (subscription Owner) was tested directly against the real Azure OpenAI
   data-plane endpoint and received a definitive `401 PermissionDenied` for
   `Microsoft.CognitiveServices/accounts/OpenAI/deployments/chat/completions/action` — expected
   Azure RBAC behavior (the built-in Owner role's `DataActions` is empty by design; only the
   deployed app's own managed identity `id-tmxap-dev` was explicitly granted "Cognitive Services
   OpenAI User," confirmed via `az role assignment list`). Granting the same role to this
   session's identity would be a real Azure IAM change outside "implement code for the current
   PBI" and was not made without explicit authorization. What WAS conclusively verified: prompt
   rendering (`configs/prompts/supervisor/turn_interpretation.md@1.0.0` renders successfully),
   request construction (correct model/deployment/temperature handling for the `gpt-5-mini`
   reasoning-family capability gap), and network reachability of the real endpoint — the entire
   code path up to the identity boundary is proven correct. Real-model classification quality for
   this exact sentence remains unverified in this sandbox, same disclosed category as PBI-14-04's
   own decisions item 4 (paraphrase classification quality) — not a new gap this PBI introduced.

6. **The pipeline's `SmokeTests` `POST /chat` calls carry no `Authorization` header — an
   incidental, pre-existing gap discovered while investigating section 8, left unfixed.**
   Confirmed via `apps/api/src/api/auth/dependency.py`'s `get_current_user()` (unconditionally
   requires a Bearer token, zero bypass) that these specific smoke-test calls would 401 against a
   real Entra-enforcing deployment; they do not currently block `DeployDev` since `SmokeTests`
   is not in `DeployDev`'s own `dependsOn`. Fixing this would mean either minting a real
   service-principal-backed token in CI or relaxing auth for smoke traffic — both are
   authentication changes, explicitly out of this PBI's scope ("Do not modify... the delegated
   Entra `access_as_user` flow"). Reported here as a disclosed finding for a future PBI, not
   silently fixed or silently ignored.

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

## PBI-14-08 (DeployDev / InfrastructureDeploy race condition — unrelated theme, see README.md)

**Root cause.** `InfrastructureDeploy` (stage 4b) and `DeployDev` (stage 5) were unsequenced
sibling stages — both `dependsOn: [InfrastructureValidation]` only, with no ordering relationship
to each other. `ops/bicep/parameters/dev.bicepparam` hardcodes `apiImageTag`/`webImageTag =
'pending-first-build'` (the original bootstrap placeholder, never updated to track the real
running image), and `ops/bicep/modules/container-app.bicep` declares each Container App as a
full, non-`existing` resource whose `image` is bound directly to that parameter. Every
`az deployment group create` run therefore resets both Container Apps back to
`pending-first-build`, regardless of what `DeployDev`'s own `az containerapp update` had just
set — whichever of the two stages happened to finish last determined the actual deployed image.

**Why `pending-first-build` reappeared.** This was scheduling luck, not a deterministic bug,
which is why it went undetected until build #50. Verified via the Azure DevOps Timeline REST API
for two real builds:

- Build #46 (`ad67be6`): stage 4b finished at `16:59:14Z`, stage 5 started `16:59:20Z` and
  finished `17:00:21Z` — `DeployDev` ran *after* Bicep's reset, so its update "won"; the correct
  image was live (this is the run PBI-14-06's own investigation happened to observe).
- Build #50 (`321ce9f`): stage 5 finished at `23:14:37Z`, stage 4b ran `23:14:42Z`–`23:17:50Z` —
  `InfrastructureDeploy` finished *after* `DeployDev`, silently reverting both Container Apps
  (new revisions `ca-tmxap-dev-api--0000037` / `ca-tmxap-dev-web--0000019`, both
  `tmx-*:pending-first-build`, both at 100% traffic under `activeRevisionsMode: Single`) — caught
  by Smoke Test 1/7 at `23:18:25Z`.

`DeployDev`'s own step log for build #50 was independently confirmed correct at the time it ran
(`az containerapp update` for both apps succeeded, `provisioningState: Succeeded`, revisions
`ca-tmxap-dev-api--0000036` / `ca-tmxap-dev-web--0000018` with the correct
`dev-50-321ce9fe...` images) — it never "falsely reported success"; the corruption happened
entirely from the later, un-sequenced `InfrastructureDeploy` run. Both `dev-50-321ce9fe...`
images were independently confirmed present in ACR throughout, proving `ContainerBuildAndPush`
was never implicated.

**Fix.** `DeployDev` now lists `InfrastructureDeploy` in its `dependsOn`, forcing Azure DevOps to
wait for it to reach a terminal state before `DeployDev` starts — its own image update now always
runs last and always wins, deterministically. `InfrastructureDeploy`'s result is deliberately
**not** checked in `DeployDev`'s condition (explicit `in(dependencies.<X>.result, 'Succeeded')`
checks replace the previous bare `succeeded()`, which would otherwise have started requiring
`InfrastructureDeploy` to succeed too, the moment it appeared in `dependsOn`) — mirroring the
identical, already-established pattern `DeploymentSummary` uses for the same dependency. This
preserves the pipeline's own explicit, pre-existing design principle: an infrastructure-only
issue (e.g. the documented Function App quota block) must never block DEV API/Web delivery.

**Why Bicep was intentionally not changed.** The driving task scoped this as a surgical CI/CD
sequencing fix only — `ops/bicep/modules/container-app.bicep` and
`ops/bicep/parameters/dev.bicepparam` were explicitly out of scope. Sequencing `DeployDev` strictly
after `InfrastructureDeploy` fully closes the observed defect (the two writers can no longer race,
so the deploy-time writer always applies last) without touching infrastructure-as-code at all — the
smallest change that eliminates the actual failure mode. The underlying Bicep design (a hardcoded
placeholder image parameter on a non-`existing` resource) remains a real, if now
sequencing-neutralized, architectural sharp edge; a future PBI could still consider parameterizing
`dev.bicepparam`'s image tags dynamically or referencing the Container Apps as `existing` post-
bootstrap, but neither is required to close this specific defect.

## PBI-14-11 (DEV deployment stabilization — the task's premise did not survive evidence)

**Driving task's framing.** DEV Web was reported as *"intermittently"* serving a Vite "Blocked
request" error despite `main` already containing PBI-14-05's and PBI-14-08's fixes, and asked for
a 7-phase forensic investigation culminating in a permanent architectural fix, explicitly
prohibiting re-touching `apps/web/vite.config.ts` "unless evidence proves main itself is wrong."

**What the evidence actually showed (Phase 1-4).** A four-way identity check (`origin/main` HEAD
`0d7b3044dfe985edeeaab48357606a633657f4d5`, the latest main pipeline run's source SHA, the live
API's `GET /version`, and the live Web bundle's embedded commit SHA) matched exactly, with no
drift. A direct live fetch of `https://ca-tmxap-dev-web.../` returned HTTP 200 with the correct
`index.html` and no "blocked" text. The Web Container App has exactly one active revision at
100% traffic (`activeRevisionsMode: Single`), ruling out a traffic-split explanation for
"intermittent." A Log Analytics query across `ca-tmxap-dev-web`'s full 7-day retention window
(2026-08-08 through 2026-08-15, 166 log lines) found zero occurrences of "Blocked request" or
"not allowed." The last three main pipeline runs (build #52, #55, #57) all show identical
results: Smoke tests 1-5 (API/Web image tag, API/Web build-commit identity, health) pass every
time; only test 6/7 (`POST /chat`) fails, with a live-reproduced HTTP 401 `"A valid Bearer token
is required"` — an authentication requirement introduced by an earlier, unrelated commit
(`fdd9d6d feat(auth)`) that the smoke test was never updated to satisfy. This resolves Phase 3's
own "smoke tests passed but the browser is broken — this contradiction MUST be resolved"
requirement, but not in the direction the task assumed: the contradiction dissolves because the
Web-blocking symptom is not currently occurring at all; the pipeline's red status has an
unrelated, real cause.

**Root-cause classification (Phase 4).** None of categories A-I (all Web-artifact-specific)
apply — there is no currently-reproducing Web defect to classify. The closest fit is J: no active
symptom, but the exact latent risk PBI-14-08 already disclosed (`ops/bicep/modules/
container-app.bicep` still binds `image` directly to `dev.bicepparam`'s hardcoded
`'pending-first-build'` on a non-`existing` resource, made safe only by stage-ordering) remains
real and worth closing regardless.

**Decision, made with the user (`AskUserQuestion`), on how to proceed.** Rather than fabricate a
Web root cause the evidence did not support, or silently stop, the findings were reported and the
user chose "harden anyway": close the Bicep ownership gap and adopt digest-pinning even without a
currently-reproducing symptom, since both were already independently justified by the evidence
above and match Phase 5's own explicit requirements. The `/chat` 401 finding was surfaced but
deliberately left unfixed here — it is an authentication/smoke-test contract mismatch, not a
deployment-image defect, and fixing it is a distinct concern outside this PBI's scope (CLAUDE.md
§7: "do not touch semantic routing/PBI-14-10 except as necessary for deployment verification";
the same "smallest viable change" principle applies to auth, which PBI-14-11 never owned).

**Fix.** Two coordinated changes, ownership boundary: infrastructure deploys must never overwrite
the image identity application deployment (`DeployDev`) owns.
1. `InfrastructureDeploy` now queries each existing Container App's currently-deployed image
   (tag or digest, parsed from `properties.template.containers[0].image`) immediately before
   `az deployment group validate`/`create`, and passes it back as a Bicep parameter override
   (`apiImageTag`/`apiImageDigest`/`webImageTag`/`webImageDigest`). An ordinary apply against an
   app that already exists is now a genuine no-op for image identity — `dev.bicepparam`'s
   placeholder is used only when the app does not exist yet (true first bootstrap). This makes
   PBI-14-08's sequencing dependency (`DeployDev` waits for `InfrastructureDeploy`) a
   belt-and-suspenders nicety rather than the sole thing preventing regression; it is left in
   place unchanged.
2. `ContainerBuildAndPush` resolves the ACR digest for each image immediately after pushing
   (`az acr repository show --query digest`) and passes it through to `DeployDev`, which now
   calls `az containerapp update --image name@sha256:...` instead of `name:tag`. This was added
   because ACR at this subscription's SKU (Basic/Standard) does not support tag-immutability
   policies (confirmed via `az acr show --query policies` — `"Policies are only supported for
   managed registries in Premium SKU"`), so a tag alone was never a guaranteed-stable reference,
   even though in practice every tag already embeds a unique `Build.BuildId` + full commit SHA.
   Smoke tests 1/7 and 2/7 were updated to assert three things together: the digest ACR currently
   reports for this run's tag, the digest `DeployDev` actually deployed, and the digest the live
   Container App references, all match — closing the mutable-tag-drift risk (Phase 4 category D)
   end to end rather than only checking the tag string.

**Why `ops/bicep/parameters/dev.bicepparam` was not changed.** The override values are supplied
by the pipeline at deploy time (`--parameters ops/bicep/parameters/dev.bicepparam --parameters
apiImageTag=... ...`, later flags win); the file's own placeholder defaults remain correct and
necessary for true first-bootstrap deploys of a brand-new environment, so it was left untouched —
the smallest change that closes the ownership gap.

**Why `apps/web/vite.config.ts`, semantic routing, and auth were not touched.** The task itself
prohibited re-touching `vite.config.ts` without proof `main` is wrong; the evidence found the
opposite (it is correct and the live symptom does not reproduce). Semantic routing (PBI-14-04/
14-10) and Entra ID authentication (`apps/api/src/api/dependencies.py`) are unrelated to
deployment image identity and were out of this PBI's explicit scope.

# Sprint 14 — Multi-Agent Semantic Intelligence

## Objective

Fix the conversational intelligence of the multi-agent platform so Claims, Broker Services, and
Commercial Intake behave like LLM-assisted conversational agents instead of rigid
form/chatbot flows — and correct the observability gaps needed to measure whether that
improvement actually worked, without turning this sprint into another observability redesign.

## Scope

- [x] PBI-14-01 (read-only gap analysis): investigated shared orchestration and all three
      specialist agents' extraction/confirmation/response logic, root-caused the observed live
      defects, and proposed the target design. Delivered entirely as a chat response per its own
      explicit "do not modify code, do not create files" instruction — no sprint artifacts exist
      for it beyond this entry and the citations in `decisions.md`/ADR-0013.
- [x] PBI-14-03 (implementation): shared semantic interpretation layer, per-agent integration,
      Supervisor routing fix, observability corrections, tests, documentation.
- [x] PBI-14-04 (implementation): moved the ONE per-turn semantic call from inside each
      specialist agent to the Supervisor, so semantic understanding runs BEFORE routing — the
      remaining root cause a live Azure validation surfaced (a keyword-free Claims message was
      misrouted to FallbackAgent, which never calls an LLM at all).

## Out of scope (this sprint)

- A second LLM call per turn for semantic interpretation, response generation, or quality
  scoring — the existing one per-turn call was repurposed instead (ADR-0013).
- LLM-informed Supervisor routing / same-turn re-routing — the Supervisor remains 100%
  deterministic (ADR-0011, ADR-0013).
- Per-field provenance telemetry, repeated-question/confirmation-retry counters, and any new
  Azure monitoring infrastructure — explicitly out of scope per the driving PBI's own
  "observability is secondary, do not redesign the dashboard" instruction.
- LLM-as-a-Judge / self-reflection quality scoring.
- Any deployment — no Azure resource was created, modified, or deployed.
- PBI-14-04: a second semantic LLM call per turn (routing stayed at exactly one call, moved not
  duplicated); a ReAct-capable Supervisor; hundreds of new keyword synonyms (only the two
  PBI-14-03 keyword gaps and its one compound rule remain — see ADR-0014); deleting
  `RuleBasedIntentResolver` (kept as the resilience fallback); a dashboard/observability
  redesign (only three new, additive `RunRecord` fields were populated); Entra ID, Azure
  resources, Container Apps topology, or Cosmos DB changes; any deployment.

## Deliverables

- [x] `src/llm/models.py` — `LLMResponseSchema` + `LLMRequest.response_schema` (additive
      structured-output request).
- [x] `src/llm/azure_openai_provider.py` — wires `response_schema` to
      `response_format=json_schema`.
- [x] `src/llm/mock_provider.py` — `structured_response_plan`/`structured_response_sequence` for
      deterministic structured-output testing.
- [x] `src/agents/shared/semantic_models.py`, `semantic_interpreter.py`, `semantic_merge.py`,
      `confirmation.py` — the shared semantic-understanding layer (one abstraction, three domain
      schemas).
- [x] `src/supervisor/intent.py` — deterministic compound-keyword disambiguation
      (incendio/fábrica-vs-Claims collision) + `póliza`/`pago` keyword gaps.
- [x] Claims/Broker/Commercial Agents + workflows integrated with the semantic layer; Commercial
      gained an explicit pre-registration confirmation step (new `CONFIRMING` status).
- [x] `src/domain/observability.py`, `src/services/observability_store/{in_memory,cosmos}.py`,
      `apps/api/src/api/routes/observability.py` — fixed the `$0.0000` cost-aggregation bug
      (unknown cost coerced to 0.0), never fabricated.
- [x] `src/supervisor/orchestrator.py` — real `intent_confidence`/`routing_reason`/
      `routing_source` telemetry via a dedicated `AgentResponse.routing_diagnostics` field
      (never persisted into chat history).
- [x] `ADR-0013` (shared semantic interpretation layer).
- [x] Tests: shared-component unit tests, Supervisor routing regression, three end-to-end
      conversational regression scenarios (one per agent), observability cost-aggregation tests.
- [x] PBI-14-04: `src/agents/shared/semantic_models.py` extended with `TurnInterpretation`/
      `AlternativeIntent`/`to_domain_interpretation`; new
      `configs/prompts/supervisor/turn_interpretation.md`; new `src/supervisor/semantic_routing.py`
      (`resolve_turn`, `SemanticRoutingConfig`); `src/supervisor/orchestrator.py` now owns the
      one pre-routing semantic call; `src/supervisor/registry.py` (`Agent` Protocol) and all
      three specialist agents + `src/agents/fallback_agent.py` gained
      `turn_interpretation`/`turn_interpretation_diagnostic` params;
      `apps/api/src/api/dependencies.py` wires `PromptManager`/`LLMProvider` into the Supervisor;
      `RunRecord`/`ObservabilityService`/`chat.py`/`observability.py` routes gained
      `routing_source`/`requires_clarification`/`alternative_intents`; `ADR-0014`; `CLAUDE.md`
      §4.1 updated to describe semantic-first routing.

## Acceptance criteria

See `validation.md` for the full evidence-backed accounting and `decisions.md` for every
deviation from the original task framing.

## Dependencies

- ADR-0011 (ReAct pattern) — the semantic layer sits strictly upstream of, and never feeds, the
  existing ReAct/Tool-Calling loop.
- ADR-0012 (observability persistence model) — this sprint populates real values into that
  schema, never redesigns it.
- `src.agents.shared.annotation.annotate_with_prompt_and_llm` (PBI-01-05/01-07) — the exact call
  site repurposed by `interpret_semantics`.
- PBI-14-04: `src.agents.shared.semantic_interpreter.interpret_semantics` (unchanged, reused
  verbatim by `src.supervisor.semantic_routing.resolve_turn`); `src.supervisor.intent.
  RuleBasedIntentResolver` (kept as the resilience fallback, not deleted).

## Risks

- A deployed model that does not support `response_format=json_schema` degrades to the same
  safe empty-interpretation fallback as any other LLM failure (never a crash, but no semantic
  enrichment that turn) — see ADR-0013's Consequences.
- Commercial Intake's conversation now takes one additional turn (explicit confirmation) before
  registration — an intentional Human-in-the-Loop change, not a regression, but a visible
  behavior difference from before this sprint.
- PBI-14-04: `SemanticRoutingConfig`'s confidence thresholds (0.7/0.4 defaults) are operational
  starting values, not calibrated against real production traffic — see ADR-0014's Consequences.
- PBI-14-04: real Azure OpenAI classification quality for the specific paraphrase test cases
  (sections 11-14) was not verified against live Azure in this sandbox (`LLM_PROVIDER=mock`
  locally, no Azure OpenAI credentials configured) — the routing/reuse LOGIC is fully tested;
  real-model classification accuracy for these exact phrasings remains a live-deployment
  concern. See `decisions.md`.

## Deliverable Log

- PBI-14-01: Multi-agent conversational intelligence gap analysis (read-only) — 2026-08-09.
- PBI-14-03: Shared semantic interpretation layer, per-agent integration, Supervisor routing
  fix, observability corrections, tests, documentation — 2026-08-13.
- PBI-14-04: Semantic-first Supervisor routing — the one per-turn semantic call now runs before
  routing and is reused (not re-requested) by the selected specialist; RuleBasedIntentResolver
  demoted to a resilience fallback; FallbackAgent gained deterministic clarification templates;
  observability gained routing_source/requires_clarification/alternative_intents; ADR-0014;
  CLAUDE.md §4.1 updated — 2026-08-14.
- PBI-14-06: Live DEV deployment evidence (confirmed PBI-14-03/PBI-14-04 both deployed) +
  build/version traceability — `GET /version` extended with `app_version`/`build_number`/
  `commit_sha`/`component`; Web build metadata via new Dockerfile ARG/ENV; a low-noise Sidebar
  version indicator with Web/API drift detection; `azure-pipelines.yml` now injects the same
  commit identity into both images and verifies it post-deploy (2 new Smoke Tests) — 2026-08-14.
- PBI-14-08: Fixed a real production DEV incident (build #50 deployed `pending-first-build`
  instead of the new image) — `InfrastructureDeploy` and `DeployDev` were unsequenced sibling
  stages that both write the same Container Apps' image, so whichever finished last won;
  `DeployDev` now depends on `InfrastructureDeploy` for ordering only (its result is never
  checked, preserving "infra issues must never block DEV delivery") — 2026-08-14.

## Sprint validation

See `validation.md`.

## Sprint retrospective

Repurposing the existing, previously-wasted per-turn LLM call (rather than adding new calls)
kept the "zero net new LLM calls per turn" target achievable while still closing every
conversational defect PBI-14-01 found. Keeping the Supervisor's routing 100% deterministic
(a narrower reading than the driving PBI's own framing technically required) turned out to be
the lower-risk choice: the one concrete regression case (incendio/fábrica) was resolvable with a
compound keyword rule, so no LLM-informed routing redesign was needed.

PBI-14-04 addendum: live validation proved PBI-14-03's own "keep the Supervisor deterministic
by never letting semantic interpretation affect routing" resolution (see this file's original
retrospective note above) was too conservative — it left the actual reported defect unfixed,
because a keyword-free message never reached a specialist agent's semantic layer at all. The
correct fix was not "make the Supervisor smarter" but "move the SAME call earlier and let fixed
conditionals consume its output," which is what ADR-0014 does — the Supervisor is exactly as
deterministic after this PBI as before it, just fed richer, pre-computed input. The
backward-compatible design (each specialist agent still calls `interpret_semantics` itself when
no `turn_interpretation` is supplied) meant every existing PBI-14-03 test — including all three
conversational regression scenarios — kept passing completely unmodified.

## PBI-14-05 (addendum — CI/CD delivery consistency, not multi-agent semantic intelligence)

Tracked here only because of its assigned PBI number (Sprint 14, item 5) — its actual subject
is `azure-pipelines.yml` delivery consistency, unrelated to this sprint's own semantic-
intelligence objective above. See `decisions.md` and `validation.md` for the full PBI-14-05
write-up.

**Problem:** DEV's Web Container App repeatedly served a stale frontend (most visibly, a Vite
"Blocked request" error `apps/web/vite.config.ts` had already fixed on `main`) because
`ContainerBuildAndPush`/`DeployDev` only built/pushed/deployed the Web image when `apps/web`
changed in the triggering commit's own diff against its immediate parent — a CI-minutes
optimization that was correctly scoped for `ContainerBuildValidation` (PR builds, which never
deploy anything) but incorrectly ALSO gated the real DEV deployment path, so any main push
whose own commit didn't happen to touch `apps/web` left DEV's Web app on whatever image a
previous run had built — silently drifting behind `main`.

**Fix:** `ContainerBuildAndPush` and `DeployDev` (both main-deploy-only stages) now always
build, push, and deploy BOTH images, unconditionally, every deploy run — both tagged with the
exact same `$(imageTag)` (`dev-$(Build.BuildId)-$(Build.SourceVersion)`, unchanged). The
`apps/web`-changed diff check is kept ONLY inside `ContainerBuildValidation` (the PR-only,
never-deploys validation path), where it still saves CI minutes without any risk of DEV drift.
Smoke Tests gained a Web deployed-image-tag verification step (mirroring the pre-existing API
one) — exactly the check that would have caught this class of drift had it existed before.

**Explicitly not touched:** `apps/web/vite.config.ts` (already correct — its own PBI-08-02
comment already documented this exact root cause from a prior occurrence), Entra ID, Azure
resource definitions/topology, `InfrastructureDeploy`'s `az deployment group create` path,
`BackendQuality`/`FrontendQuality`/`SecurityScan`/`InfrastructureValidation` gates.

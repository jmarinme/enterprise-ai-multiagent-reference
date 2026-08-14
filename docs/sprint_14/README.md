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

## Risks

- A deployed model that does not support `response_format=json_schema` degrades to the same
  safe empty-interpretation fallback as any other LLM failure (never a crash, but no semantic
  enrichment that turn) — see ADR-0013's Consequences.
- Commercial Intake's conversation now takes one additional turn (explicit confirmation) before
  registration — an intentional Human-in-the-Loop change, not a regression, but a visible
  behavior difference from before this sprint.

## Deliverable Log

- PBI-14-01: Multi-agent conversational intelligence gap analysis (read-only) — 2026-08-09.
- PBI-14-03: Shared semantic interpretation layer, per-agent integration, Supervisor routing
  fix, observability corrections, tests, documentation — 2026-08-13.

## Sprint validation

See `validation.md`.

## Sprint retrospective

Repurposing the existing, previously-wasted per-turn LLM call (rather than adding new calls)
kept the "zero net new LLM calls per turn" target achievable while still closing every
conversational defect PBI-14-01 found. Keeping the Supervisor's routing 100% deterministic
(a narrower reading than the driving PBI's own framing technically required) turned out to be
the lower-risk choice: the one concrete regression case (incendio/fábrica) was resolvable with a
compound keyword rule, so no LLM-informed routing redesign was needed.

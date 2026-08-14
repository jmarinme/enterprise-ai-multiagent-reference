# Sprint 14 — Implementation Plan

## PBI-14-01 — Gap analysis (read-only)

Investigated `src.supervisor.*`, `src.core.tool_calling.*`, `src.llm.*`,
`src.agents.shared.{memory,state_persistence,nlu,conversational_policy,annotation}`,
all three specialist agents' `state.py`/`extraction.py`/`workflow.py`/`*_agent.py`, and the
observability stack (`src.domain.observability`, `src.observability.service`,
`src.observability.pricing`, `src.services.observability_store.*`,
`apps/api/src/api/routes/observability.py`, the two dashboard pages). Delivered as a chat
response (16-item structured return per the task's own instruction); no files created.

## PBI-14-03 — Implementation

Sequenced to keep the "reuse the existing LLM call" constraint verifiable at every step:

1. **LLM structured-output plumbing** (`src/llm/models.py`, `azure_openai_provider.py`,
   `mock_provider.py`) — additive `response_schema`/`LLMResponseSchema`, wired to Azure OpenAI's
   `response_format=json_schema`; `MockLLMProvider` scripting for deterministic tests.
2. **Shared semantic layer** (`src/agents/shared/{semantic_models,semantic_interpreter,
   semantic_merge,confirmation}.py`) — one interpretation shape, three domain entity schemas
   (mapped onto each Agent's real state fields, verified against PBI-14-01's own citations, not
   invented), the repurposed LLM-call wrapper, the confidence-gated merge, and the shared
   confirmation resolver.
3. **Supervisor routing fix** (`src/supervisor/intent.py`) — a narrow, deterministic compound-
   pattern rule plus two confirmed keyword gaps. Verified against the existing
   `Hubo un incendio en mi negocio.` -> CLAIMS test case to confirm no regression (that message
   has no "asegurar"-family verb, so the new rule correctly does not fire).
4. **Claims integration** (`src/agents/claims_agent.py`, `claims/workflow.py`,
   `claims/extraction.py`) — `interpret_semantics` moved before `advance_claims_intake` (replaces
   the old post-hoc `annotate_with_prompt_and_llm` call, same call count); semantic-fallback
   merge for the free-text/ambiguous fields; `confirmed` field handling moved from the generic
   `_YES_NO_FIELDS` first-word check to the shared confirmation module.
5. **Broker integration** (`src/agents/broker_agent.py`, `broker/workflow.py`,
   `broker/extraction.py`) — same pattern; `wants_payment_request` moved to the shared
   confirmation module (the `_YES_NO_FIELDS` set it was the sole member of was removed).
6. **Commercial Intake integration** (`src/agents/commercial_intake_agent.py`,
   `commercial/workflow.py`, `commercial/state.py`) — same pattern, PLUS: new `CONFIRMING` status
   (mirroring Claims' existing pre-registration confirmation pattern) and
   `industry`/`location`/`insured_value` qualification-only state fields.
7. **Observability corrections** (`src/domain/observability.py`,
   `src/services/observability_store/{in_memory,cosmos}.py`,
   `apps/api/src/api/routes/observability.py`, `apps/web/src/api/observability.ts`) — the
   `$0.0000` bug (`ConversationSummary.total_estimated_cost_usd` coercing `None` to `0.0`) fixed
   at every aggregation point (in-memory increment, Cosmos increment, Cosmos KPI SUM query, the
   API response Pydantic model, which would otherwise have raised a validation error on a `None`
   value — found while implementing, not anticipated). `src/supervisor/orchestrator.py` gained
   real `intent_confidence`/`routing_reason`/`routing_source` telemetry via a new
   `AgentResponse.routing_diagnostics` field (deliberately separate from `metadata`, which
   persists into the Conversation document — routing diagnostics must not bloat chat history).
8. **Tests** — shared-component unit tests (confirmation, semantic merge, semantic interpreter
   incl. a schema-shape assertion that no chain-of-thought field exists), a Supervisor routing
   regression test for the hard incendio/fábrica case, one full conversational regression test
   per agent (`test_{claims,broker,commercial_intake}_agent_semantic_regression.py`) driven end
   to end with `MockLLMProvider.structured_response_sequence`, and observability cost-
   aggregation tests (known price / unknown price / one-unknown-poisons-the-total / KPI
   aggregation).
9. **Documentation** — `ADR-0013`, this sprint folder.

## Testing strategy

- Additive-only pattern throughout: every existing extraction/workflow test kept passing
  unmodified except where behavior was deliberately and disclosedly changed (see
  `decisions.md`).
- Structured-output scripting (`structured_response_sequence`) added to `MockLLMProvider`
  specifically so a multi-turn regression scenario could exercise a *different* plausible
  semantic interpretation per turn, matching what a real (non-static) LLM would actually
  produce.
- Regression scenarios were built from the exact synthetic fixtures already used elsewhere
  (Juan Pérez's two auto policies, Synthetic Brokerage One's 2026-Q1 commission) rather than
  inventing new synthetic data.

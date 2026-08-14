# Sprint 14 — Validation

All commands below were actually executed in this session. PBI-14-03's own run was against
branch `feat/pbi-14-03-multiagent-semantic-intelligence`; PBI-14-04's own run (see its own
subsection below) was against `feat/pbi-14-04-universal-semantic-routing`, branched from `main`
after PBI-14-03 was merged. No result is asserted without having run it.

## PBI-14-03 backend

| Command | Result |
|---|---|
| `python -m pytest tests/unit tests/conversational -q` | **796 passed**, 0 failed, 1 pre-existing unrelated warning (StarletteDeprecationWarning) |
| `python -m ruff check .` | **All checks passed** (full repository) |
| `python -m mypy src apps/api` | **7 pre-existing errors in `src/pipelines/knowledge_ingestion/index_schema.py`** (confirmed via `git status`/`git diff` — this file was never touched this session; `SimpleField`/`SearchFieldDataType` Enum-vs-str typing gap, unrelated to this PBI). Every touched file individually verified clean before this full-repo run. |

Targeted mypy/ruff runs during implementation (all clean, listed for traceability):
`src/llm/{models,azure_openai_provider,mock_provider}.py`,
`src/agents/shared/{semantic_models,semantic_interpreter,semantic_merge,confirmation}.py`,
`src/agents/{claims_agent,claims/workflow,claims/extraction}.py`,
`src/agents/{broker_agent,broker/workflow,broker/extraction}.py`,
`src/agents/{commercial_intake_agent,commercial/workflow,commercial/state}.py`,
`src/supervisor/{intent,orchestrator,models}.py`,
`src/domain/observability.py`,
`src/services/observability_store/{in_memory,cosmos}.py`,
`apps/api/src/api/routes/{chat,observability}.py`.

## PBI-14-03 frontend

| Command | Result |
|---|---|
| `npm run test -- --run` (apps/web) | **8 test files, 42 tests passed** |
| `npm run typecheck` (apps/web) | Clean (`tsc --noEmit`, no errors) |
| `npm run lint` (apps/web) | Clean (`eslint .`, no errors) |
| `npm run build` (apps/web) | Succeeded — `tsc --noEmit && vite build`, 219 modules transformed, no errors |

## PBI-14-03 new tests added

- `tests/unit/agents/shared/test_confirmation.py` (13 tests)
- `tests/unit/agents/shared/test_semantic_merge.py` (4 tests)
- `tests/unit/agents/shared/test_semantic_interpreter.py` (5 tests, incl. a schema-shape
  assertion that no chain-of-thought/reasoning field exists)
- `tests/unit/agents/test_claims_agent_semantic_regression.py` (1 end-to-end scenario test)
- `tests/unit/agents/test_broker_agent_semantic_regression.py` (1 end-to-end scenario test)
- `tests/unit/agents/test_commercial_intake_agent_semantic_regression.py` (1 end-to-end scenario
  test)
- `tests/unit/services/test_observability_store_in_memory.py` — 5 new cost-nullability tests
  appended to the existing file
- `tests/unit/supervisor/test_intent.py` — 4 new parametrized cases appended (incendio/fábrica
  hard case, English equivalent, `póliza`/`pago` keyword-gap cases)
- 2 pre-existing extraction-level tests removed (relocated coverage — see `decisions.md` item 5)

Net: 796 backend tests passing (up from 738 at the start of this PBI's implementation phase,
before that: 682 + 18 from PBI-12-04 per ADR-0011's own log — continuous growth, no regression).

## PBI-14-03 not run (and why)

- Real Azure OpenAI structured-output call — `AzureOpenAIProvider` is never exercised against
  real Azure by this test suite (documented, pre-existing limitation, same as every other
  Azure-dependent adapter in this repo).
- Cosmos DB — same documented limitation; `CosmosObservabilityRepository`'s fix is
  code-reviewed and pattern-consistent with the test-verified in-memory equivalent, not
  runtime-verified (see `decisions.md` item 6).
- Azure deployment / `docker build` / `az containerapp update` / `az deployment group create` —
  explicitly out of scope per CLAUDE.md §7.1 (Azure DevOps CI/CD owns deployment) and the
  driving PBI's own "Do NOT deploy" instruction.

## PBI-14-04 backend

| Command | Result |
|---|---|
| `python -m pytest tests/unit tests/conversational -q` | **851 passed**, 0 failed, 1 pre-existing unrelated warning |
| `python -m ruff check .` | **All checks passed** (full repository) |
| `python -m mypy src apps/api` | Same **7 pre-existing errors** in `src/pipelines/knowledge_ingestion/index_schema.py`, still confirmed untouched this session — every touched file individually verified clean first. |

## PBI-14-04 frontend

No frontend source file was touched by this PBI (backend/routing-only change). Full suite run
anyway to confirm no incidental regression:

| Command | Result |
|---|---|
| `npm run test -- --run` (apps/web) | **9 test files, 50 tests passed** |
| `npm run typecheck` (apps/web) | Clean |
| `npm run lint` (apps/web) | Clean |
| `npm run build` (apps/web) | Succeeded — 219 modules transformed, no errors |

## PBI-14-04 new tests added

- `tests/unit/supervisor/test_semantic_routing.py` (10 tests) — every confidence band,
  explicit-clarification flag, both degraded-call detection paths (LLM exception, malformed
  JSON).
- `tests/unit/supervisor/test_semantic_routing_domain_paraphrases.py` (31 parametrized tests) —
  sections 11-14's exact Claims/Broker/Commercial/unknown phrases, plus the two current-goal
  pair cases and the exact production regression sentence.
- `tests/unit/supervisor/test_pbi_14_04_production_regression.py` (3 tests) — the full
  Supervisor + real ClaimsAgent + real Tools pipeline: production regression sentence reaches
  ClaimsAgent, exactly one structured semantic call per turn (call-counting
  `MockLLMProvider` subclass), ReAct/Tool-Calling still runs, and a 3-turn intent-switch
  (Claims -> Broker -> Commercial) with isolated per-domain state.
- `tests/unit/agents/test_fallback_agent.py` (6 tests) — plain vs. clarification messages, all
  three domain-pair templates plus the generic fallback, and a check that
  `turn_interpretation.routing_reason` never leaks into the user-facing response.
- `tests/unit/agents/shared/test_turn_interpretation.py` (5 tests) — `to_domain_interpretation`
  field mapping/adaptation, `None`-turn safe degradation, and a chain-of-thought schema-shape
  assertion.
- `tests/unit/supervisor/test_orchestrator.py` — updated (not counted as new) to construct
  `SupervisorOrchestrator` with the two new `prompt_manager`/`llm_provider` dependencies; every
  existing assertion kept its original meaning (a bare `MockLLMProvider()` with no scripted
  structured response degrades the semantic call, exercising the same
  `RuleBasedIntentResolver` keyword path these tests already verified before this PBI).

Net: 851 backend tests passing (up from 796 at the start of this PBI's implementation phase),
zero regressions, zero pre-existing tests modified for behavior reasons (only the orchestrator
constructor-argument updates above, which are call-site adaptations, not behavior changes).

## PBI-14-04 not run (and why)

- Real Azure OpenAI classification of the section 11-14 paraphrase test cases — this sandbox has
  `LLM_PROVIDER=mock` configured locally with no Azure OpenAI credentials available (same
  documented, pre-existing limitation noted under PBI-14-03 above). The domain-paraphrase tests
  verify the deterministic routing/reuse LOGIC given a classification, not real-model
  classification accuracy for these exact phrasings — see `decisions.md` item 4 and the
  "live-like local validation" note in the final PBI-14-04 report.
- Cosmos DB, Azure deployment, `docker build` — same reasons as PBI-14-03 above; nothing new in
  this PBI changed that boundary.

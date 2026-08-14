# Sprint 14 — Validation

All commands below were actually executed in this session against the working tree on
`feat/pbi-14-03-multiagent-semantic-intelligence`. No result is asserted without having run it.

## Backend

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

## Frontend

| Command | Result |
|---|---|
| `npm run test -- --run` (apps/web) | **8 test files, 42 tests passed** |
| `npm run typecheck` (apps/web) | Clean (`tsc --noEmit`, no errors) |
| `npm run lint` (apps/web) | Clean (`eslint .`, no errors) |
| `npm run build` (apps/web) | Succeeded — `tsc --noEmit && vite build`, 219 modules transformed, no errors |

## New tests added this sprint

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

## Not run (and why)

- Real Azure OpenAI structured-output call — `AzureOpenAIProvider` is never exercised against
  real Azure by this test suite (documented, pre-existing limitation, same as every other
  Azure-dependent adapter in this repo).
- Cosmos DB — same documented limitation; `CosmosObservabilityRepository`'s fix is
  code-reviewed and pattern-consistent with the test-verified in-memory equivalent, not
  runtime-verified (see `decisions.md` item 6).
- Azure deployment / `docker build` / `az containerapp update` / `az deployment group create` —
  explicitly out of scope per CLAUDE.md §7.1 (Azure DevOps CI/CD owns deployment) and the
  driving PBI's own "Do NOT deploy" instruction.

# Sprint 12 — Validation

## PBI-12-01 (read-only)

No code or repository files were modified. Validation consisted of direct code reads with exact
file:line citations, all reported in the chat response itself — no separate evidence artifact.

## PBI-12-04

| Command | Result |
|---|---|
| `python -m pytest tests/unit/core/tool_calling/ -q` (after orchestrator hardening, before agent wiring) | 28 passed — 0 regressions from duplicate-detection/timeout additions |
| `python -m pytest tests/unit/agents/ tests/unit/api/test_dependencies.py tests/unit/core/tool_calling/ -q` (after Broker/Commercial wiring) | 247 passed |
| `python -m pytest tests/ -q` (full backend suite, after wiring) | 682 passed, 2 skipped — 0 regressions |
| `python -m pytest tests/ -q` (full backend suite, after all 18 new tests added) | **700 passed, 2 skipped** — 18 new tests, 0 regressions |
| `ruff check apps/api/src src tests` | All checks passed |
| `mypy apps/api/src src` | 7 pre-existing errors in `src/pipelines/knowledge_ingestion/index_schema.py` (Azure AI Search SDK enum-typing issue) — unrelated file, not touched this sprint, confirmed pre-existing |
| `mypy src/core/tool_calling/orchestrator.py src/core/tool_calling/models.py src/agents/broker_agent.py src/agents/commercial_intake_agent.py apps/api/src/api/dependencies.py` (every file touched) | Success: no issues found in 5 source files |
| `npx vitest run --reporter=basic` (apps/web) | 8 test files, 40 tests passed — unaffected (this sprint touched no frontend code) |
| `npm run build` (apps/web) | `tsc --noEmit && vite build` succeeded |

## Constraint verification (against the task's explicit "ABSOLUTE CONSTRAINTS")

| Constraint | Verified |
|---|---|
| Microsoft Entra ID / Authentication / JWT validation not modified | No file under `apps/api/src/api/auth/` or `apps/web/src/auth/` touched — confirmed via the file list in the final report |
| Cosmos memory not modified | `src/domain/conversation.py`, `src/services/conversation_store/` untouched; `AgentResponse.metadata` shape unchanged (no new keys added) |
| Supervisor routing not modified | `src/supervisor/orchestrator.py`, `src/supervisor/intent.py` untouched |
| APIs not modified | No file under `apps/api/src/api/routes/` touched |
| Security not modified | No security-relevant file touched outside the two new resilience fields on `ToolCallingContext`/`ToolCallingResponse` |
| Existing workflows not modified | `src/agents/claims/workflow.py`, `src/agents/broker/workflow.py`, `src/agents/commercial/workflow.py` untouched |
| Existing conversation state not modified | `ClaimsIntakeState`/`BrokerInquiryState`/`CommercialIntakeState` models untouched; the new isolated ReAct paths never write to them, proven by the pre-existing (Claims) and new (Broker/Commercial) `test_tool_calling_never_alters_the_deterministic_business_fact_text` tests |
| Tool interfaces not modified | `src/tools/protocol.py`, `src/tools/registry.py`, `src/tools/executor.py` untouched |
| Supervisor stays outside the ReAct loop | `src/supervisor/orchestrator.py` never imports `ToolCallingOrchestrator` — confirmed by grep |
| Deterministic business actions preserved | `advance_claims_intake`/`advance_broker_inquiry`/`advance_commercial_intake` call signatures and internal logic unchanged |
| Reasoning never leaked to the user | `test_isolated_tool_calling_reasoning_text_never_leaks_into_the_visible_response` (Broker + Commercial), passing |
| Reasoning never persisted | `test_isolated_tool_calling_reasoning_text_is_never_persisted_in_metadata` (Broker + Commercial), passing |
| No infinite loop introduced | `max_iterations` (pre-existing, reused) + new `timeout_seconds` (opt-in) + new duplicate-call detection all bound the loop; `test_run_stops_at_max_iterations_against_a_never_terminating_llm` (pre-existing) and `test_run_stops_and_flags_timeout_when_a_single_llm_call_hangs` (new) both pass |

## Escalation clause check

The task's own instruction: "If during implementation you discover that extending the existing
ReAct implementation introduces an unacceptable regression risk, STOP immediately... and
recommend the smallest safe alternative instead of forcing the implementation."

One real, pre-existing regression risk was discovered mid-implementation (Claims' isolated
tool-calling path does not catch a genuine `LLMProvider` failure, only `ToolCallingError` — see
`decisions.md` D-04). Judged not to meet the STOP bar: it is a pre-existing gap being extended in
surface area (from one agent to three), not a new category of risk, and it was addressed for the
two *new* call sites (Broker/Commercial) without touching Claims' explicitly-protected behavior.
Implementation proceeded; the finding is documented, not hidden, and a follow-up is recommended
in the final report rather than silently left unaddressed.

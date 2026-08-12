# Sprint 12 — Implementation Plan

## PBI-12-01: ReAct Gap Analysis Against Course Requirement (read-only)

1. Inspect `src/core/tool_calling/orchestrator.py` in full — determine whether `run()` already
   implements a bounded LLM↔Tool loop with observation feedback, or is single-shot.
2. Inspect `ClaimsAgent`/`BrokerAgent`/`CommercialIntakeAgent` — which hold a
   `ToolCallingOrchestrator` vs. a plain `ToolExecutor`.
3. Inspect `SupervisorOrchestrator`/`RuleBasedIntentResolver` — confirm routing has no LLM
   involvement and no retry/re-routing loop.
4. Inspect the Claims/Broker workflow state machines — confirm the LLM never drives a business
   decision inside them.
5. Inspect `PromptManager`/`configs/prompts/` for any existing Thought/Action/Observation
   scaffolding (none found).
6. Inspect `src/domain/conversation.py`/`state_persistence.py` for a field that could hold a
   reasoning trace (none exists — `metadata` is `dict[str, str]`, deliberately not designed for
   this, per CLAUDE.md §10).
7. Inventory existing tests covering the orchestrator's loop behavior.
8. Confirm the existing resilience-parameter naming convention (`retry.py`/`circuit_breaker.py`)
   for consistency if new bounds were to be added.
9. Synthesize findings into the 10 numbered questions the task specified, plus a scoped GO/NO-GO
   recommendation. Delivered as a chat response — no repository file, per the read-only
   instruction.

## PBI-12-04: Generalize the Existing ReAct Implementation Across All Specialist Agents

1. Harden `src/core/tool_calling/orchestrator.py`/`models.py`: add
   `ToolCallingContext.timeout_seconds` (opt-in, default `None`), a per-LLM-call
   `asyncio.wait_for` wrapper, `ToolCallingResponse.stopped_due_to_timeout`, and duplicate-call
   detection (a `seen_call_signatures` set local to each `run()` invocation) — reusing the
   existing `max_iterations` bound unchanged. Validate against the existing 28-test suite before
   proceeding (0 regressions).
2. Wire `BrokerAgent`/`CommercialIntakeAgent` to `ToolCallingOrchestrator`, mirroring
   `ClaimsAgent`'s exact additive/isolated `_run_controlled_tool_calling` pattern — never
   feeding `BrokerInquiryState`/`CommercialIntakeState`. Add the broader `except Exception`
   hardening discovered necessary mid-implementation (see `decisions.md` D-04).
3. Update `apps/api/src/api/dependencies.py` to pass the shared, cached
   `ToolCallingOrchestrator` instance into both new agents.
4. Update every existing test that constructs `BrokerAgent`/`CommercialIntakeAgent` directly
   (4 files: `test_broker_agent_functional.py`, `test_commercial_intake_agent_functional.py`,
   `test_mock_agents.py`, plus the two prompt-version-string assertions in
   `test_claims_agent_prompt_integration.py`) to supply the new required constructor parameter.
5. Update all three prompts (`configs/prompts/claims|broker_services|commercial_intake/
   system.md`) with explicit Reason/Act/Observe framing and an explicit
   never-reveal-reasoning instruction; bump prompt versions and `change_notes`.
6. Add new tests: 5 orchestrator-level (duplicate detection ×3, timeout ×2) in
   `test_tool_calling_orchestrator.py`; 7 Broker + 6 Commercial agent-level tests in two new
   files, mirroring `test_claims_agent_tool_calling_integration.py`'s structure, including
   dedicated no-reasoning-leakage and no-reasoning-persistence tests.
7. Run full validation: `pytest tests/` (700 passed, 2 skipped), `ruff check apps/api/src src
   tests`, `mypy apps/api/src src` (+ targeted mypy on every touched file), `npx vitest run`
   (40 passed), `npm run build` (green).
8. Create `docs/Architecture/adr/0011-react-pattern-for-tool-orchestrated-reasoning.md`.
9. Update `README.md` (Funcionalidades, Arquitectura visión general, new "Patrones de IA
   Agéntica" section), `CLAUDE.md` §3, `review/00_project_inventory.md`,
   `review/05_executive_summary.md`, `review/06_enterprise_architecture_assessment.md`,
   `docs/Architecture/Deployment_Guide.md` (agent descriptions + cross-references).
10. Annotate (not redraw) `docs/Architecture/diagrams/authentication-request-flow.md` — add
    "(ReAct: Reason/Act/Observe)" to the three Agent boxes plus a reading note.
11. Update `docs/Presentation/Final_Project_Presentation.pptx`'s "Patrones de IA Agéntica" slide
    and `docs/Presentation/Speech_Guide.md` in place — surgical edit, not a full regeneration.
12. Create this sprint's own documentation (`docs/sprint_12/`) per CLAUDE.md §12/§13.
13. Compose the final report: files modified, architecture changes, tests added, documentation
    updated, presentation updated, ADR added, regression results, remaining technical debt.

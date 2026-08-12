# Sprint 12 — Agentic Pattern Alignment (ReAct)

## Objective

Verify the platform's Tool Calling mechanism against the course's named primary agentic pattern
(ReAct + Tool Calling), then generalize whatever gap analysis found across all three specialist
agents — without redesigning the architecture, replacing the existing orchestration, or building
a second reasoning engine.

## Scope

- [x] PBI-12-01: ReAct Gap Analysis Against Course Requirement (read-only).
- [x] PBI-12-04: Generalize the Existing ReAct Implementation Across All Specialist Agents.

## Out of scope

- Redesigning `ToolCallingOrchestrator` or building a new orchestration engine.
- Changing `ClaimsAgent`'s runtime behavior (only prompt wording, per explicit instruction).
- Wiring ReAct into the deterministic workflow/state-machine layer (would violate CLAUDE.md §3,
  "the LLM is not the source of truth").
- Moving any reasoning into the Supervisor (must remain deterministic, ADR-0011).
- LLM-as-a-Judge, Self-Reflection — named as future evolution only (ADR-0011), not built.
- Fixing the pre-existing Claims error-handling gap discovered during PBI-12-04 (see
  `decisions.md`) — explicitly out of scope per this PBI's own constraint.

## Deliverables

- [x] PBI-12-01: read-only gap analysis, delivered as a structured chat response (10 numbered
      questions + GO/NO-GO recommendation) — no repository file produced, per the task's
      read-only instruction.
- [x] PBI-12-04: `ToolCallingOrchestrator` hardened (duplicate-tool-call detection, opt-in
      per-call timeout); `BrokerAgent`/`CommercialIntakeAgent` wired to the same shared
      orchestrator instance as `ClaimsAgent`, additive and isolated; all three prompts updated
      with explicit Reason/Act/Observe framing; `docs/Architecture/adr/0011-react-pattern-for-
      tool-orchestrated-reasoning.md` created; README.md, CLAUDE.md, and the review/ document
      set updated; the authentication-request-flow diagram annotated (not redrawn); the
      PowerPoint "Patrones de IA Agéntica" slide and its speaker notes updated in place; 18 new
      tests added, all 700 backend tests passing, `ruff`/`mypy` clean, frontend unaffected (40
      tests, build green).

## Acceptance criteria

See `validation.md` for the full, evidence-backed accounting against every constraint the task
specified (no Entra ID/auth/JWT/Cosmos/routing/API/security/existing-workflow/state/Tool-
interface change; Supervisor stays deterministic and outside the ReAct loop; deterministic
business actions preserved; reasoning never persisted or leaked).

## Dependencies

- `src/core/tool_calling/orchestrator.py` (PBI-02-04) — the existing, tested ReAct loop this
  sprint generalized rather than replaced.
- `src.core.tool_calling.policies.BROKER_ALLOWED_TOOLS`/`COMMERCIAL_ALLOWED_TOOLS` (PBI-02-04) —
  already defined and tested, explicitly documented at the time as "ready for a future PBI to
  wire without re-deriving it."

## Risks

See `decisions.md` — principally the pre-existing Claims error-handling gap found (not
introduced) while generalizing this pattern, and the decision to harden only the new Broker/
Commercial wiring rather than touch Claims' behavior.

## Deliverable Log

<!-- Append entries. Do not remove previous entries. -->

PBI-12-01: ReAct gap analysis delivered as a structured, evidence-cited chat response (read-only,
no code/doc changes) — 2026. Found `ToolCallingOrchestrator.run()` already implements a bounded
Reason→Act→Observe→Reason loop (15 pre-existing tests), wired only into `ClaimsAgent` as an
isolated/additive capability; recommended GO on a narrowly-scoped generalization.

PBI-12-04: Generalized `ToolCallingOrchestrator` to `BrokerAgent`/`CommercialIntakeAgent`
(`src/agents/broker_agent.py`, `src/agents/commercial_intake_agent.py`,
`apps/api/src/api/dependencies.py`); hardened the shared orchestrator with duplicate-tool-call
detection and an opt-in per-call timeout (`src/core/tool_calling/orchestrator.py`,
`src/core/tool_calling/models.py`); updated all three specialist prompts with explicit
Reason/Act/Observe framing (`configs/prompts/claims|broker_services|commercial_intake/
system.md`); added 18 new tests (5 orchestrator hardening, 7 Broker ReAct, 6 Commercial ReAct)
— 700 backend tests passing (was 682), 0 regressions, `ruff`/`mypy` clean, frontend unaffected
(40 tests, build green); created `docs/Architecture/adr/0011-react-pattern-for-tool-
orchestrated-reasoning.md`; updated `README.md`, `CLAUDE.md` §3, `review/00_project_inventory.md`,
`review/05_executive_summary.md`, `review/06_enterprise_architecture_assessment.md`,
`docs/Architecture/Deployment_Guide.md`, `docs/Architecture/diagrams/authentication-request-
flow.md` (annotated, not redrawn); updated `docs/Presentation/Final_Project_Presentation.pptx`'s
"Patrones de IA Agéntica" slide and `Speech_Guide.md` in place — 2026. Evidence: `validation.md`,
`decisions.md`.

## Sprint validation

See `validation.md`.

## Sprint retrospective

The most valuable finding this sprint was negative: the platform did not need a new ReAct
engine, because one already existed, was already tested, and had simply never been named or
generalized. Treating PBI-12-01 as genuinely read-only analysis first — rather than jumping
straight to implementation — is what surfaced that distinction; a less careful pass could have
built a second, redundant orchestration engine to satisfy the same course requirement the
existing one already met mechanically. The one real regression risk found mid-implementation
(Claims' isolated tool-calling path only catching `ToolCallingError`, not a genuine LLM provider
failure) was a pre-existing gap, not something this sprint introduced — the right response was to
harden the *new* Broker/Commercial wiring from day one rather than silently carrying the same
fragility into two more agents, while leaving Claims itself untouched per this PBI's own explicit
constraint. That asymmetry is now documented, not hidden.

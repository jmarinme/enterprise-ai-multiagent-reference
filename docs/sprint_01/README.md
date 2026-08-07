# Sprint 01 — Core Multi-Agent Platform

## Objective

Build the core multi-agent orchestration platform: the Conversation API, context management,
the Supervisor orchestration framework, intent classification, registry-driven agent routing,
guardrails, and a human-escalation foundation — per `CLAUDE.md` §14's Sprint 01 scope.

## Scope

- Supervisor orchestration framework (interfaces, registry-driven routing, no concrete-agent
  coupling).
- Rule-based intent resolution (no LLM yet).
- Mock domain agents validating the registry pattern (Claims, Broker, Commercial Intake).
- `POST /chat` conversational entry point.
- Conversation persistence through the existing `ConversationRepository` (PBI-00-05).
- Further Sprint 01 PBIs (real agent business logic, LLM-backed intent classification,
  guardrails, human escalation, Tool registry/contracts) will be defined and added to the
  Deliverables list below as they are scoped — only PBI-01-01 is defined at Sprint start.

## Out of scope

- Azure OpenAI / Semantic Kernel / AutoGen / LangGraph / CrewAI.
- Prompt engineering, RAG, Azure AI Search, vector databases.
- Real Tool Calling against business systems.
- Authentication (Entra ID end-user login).
- Real insurance business logic in any agent.

## Deliverables

- [x] PBI-01-01: Build the Supervisor Agent orchestration framework.

## Acceptance criteria

| ID | Criterion | Evidence expected |
|---|---|---|
| AC-01 | Supervisor depends only on interfaces (Agent/IntentResolver/AgentRegistry Protocols), never on concrete agents | Code review — no concrete agent import in `src/supervisor/` |
| AC-02 | Agent routing is registry-driven, no if/else on intent | Code review — `orchestrator.py` |
| AC-03 | `POST /chat` exercises the full pipeline (Supervisor → Intent → Registry → Agent → Repository → JSON) | Unit + integration-style API test, evidence log |
| AC-04 | 100% deterministic tests, no Azure dependency | `pytest` evidence |
| AC-05 | `ruff`/`mypy` clean | Evidence log |
| AC-06 | API Docker image remains buildable after the shared-package wiring | `docker build`/`docker compose config` evidence |

## Dependencies

- Everything already established in Sprint 00: `apps/api`, `src/domain`, `src/services`,
  `src/config`, root `pyproject.toml`, CI pipeline.

## Risks

| Risk | Probability | Impact | Mitigation |
|---|---:|---:|---|
| Sprint 00 formally still has 2 open PBIs (00-08, 00-09) when Sprint 01 starts | N/A (accepted) | Media | User explicitly accepted this risk for PBI-01-01; see `docs/sprint_00/decisions.md`. Sprint 00 closure is unaffected by Sprint 01 progress and remains trackable independently. |
| Cross-package dependency (`apps/api` → root `src/`) breaks the Docker image | Media | Alta | Addressed directly in PBI-01-01 as a prerequisite fix (build context + `PYTHONPATH`), validated via `docker compose config` / `docker build` |

## Deliverable Log

<!-- Append entries. Do not remove previous entries. -->

PBI-01-01: Supervisor orchestration framework built (`src/supervisor/`): `Supervisor`/`Agent`/`IntentResolver`/`AgentRegistry` Protocols, `SupervisorOrchestrator` (depends only on interfaces, never a concrete agent, registry-driven routing with no if/else/switch), `RuleBasedIntentResolver` (deterministic keyword matching, no AI), `InMemoryAgentRegistry`, and 4 deterministic mock agents (`ClaimsAgent`, `BrokerAgent`, `CommercialIntakeAgent`, and `FallbackAgent` for `UNKNOWN` — the 4th is a deliberate addition beyond the 3 explicitly requested, keeping the registry total). `POST /chat` exposed via `apps/api/src/api/routes/chat.py`, composed in `apps/api/src/api/dependencies.py`. Fixed a real Docker build-context gap (API image had no access to the shared `src/` package) as a prerequisite, not scope creep. 60/60 new+existing unit tests pass deterministically with no Azure dependency (2 unrelated live-integration scaffolds skip as designed); ruff and mypy clean; live smoke test confirmed the full `POST /chat → Supervisor → Intent → Registry → Agent → Repository → JSON` pipeline against a running server. No Azure OpenAI, RAG, APIM, or business logic implemented. Started with Sprint 00 not yet formally closed (PBI-00-08/09 open) — user explicitly accepted this risk; see `docs/sprint_00/decisions.md`. — 2026-08-07
Evidence: `docs/sprint_01/evidence/pbi-01-01-supervisor-orchestration-validation.txt`

## Sprint validation

See `validation.md`.

## Sprint retrospective

Complete when closing the sprint:

- What worked:
- What did not:
- Technical debt:
- Security findings:
- Follow-up PBIs:

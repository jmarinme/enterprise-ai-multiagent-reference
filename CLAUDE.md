# CLAUDE.md — TMX Enterprise AI Reference Platform

## 1. Project

This repository contains the **TMX Enterprise AI Reference Platform**, an academic reference implementation for a corporate insurance multi-agent solution.

The project has two simultaneous goals:

1. Deliver a complete final academic project.
2. Provide a reusable reference for future enterprise AI developments.

This repository does **not** represent an officially approved TMX production architecture. It must not contain real internal systems, real customer information, production credentials, or undocumented company assumptions.

Primary goal: build and evolve a secure, modular, auditable, observable, and deployable multi-agent platform on Microsoft Azure, using synthetic data and simulated business APIs.

Primary architecture reference:

`TMX_Enterprise_AI_Reference_Architecture_and_Delivery_Standard_V2.0.docx`

If code or a sprint instruction conflicts with the architecture document, stop, report the conflict, and propose the smallest compliant correction.

---

## 2. Business scope

| Agent | Purpose | Permitted scope |
|---|---|---|
| Supervisor Agent | Authenticate context, classify intent, apply guardrails, route, coordinate, and escalate | Must not execute business transactions or access databases directly |
| Claims Agent | Guide a synthetic after-hours claim notification flow | May call approved claims Tools; must not determine final coverage, reject claims, or authorize indemnity |
| Broker Services Agent | Support synthetic policy, procedure, receipt, payment-reference, and commission queries | Must not execute payments, approve commissions, modify policies, or expose another broker’s information |
| Commercial Intake Agent | Classify commercial requests, identify line of business, collect missing information, preregister a lead, and route it | Must not quote, underwrite, define premiums, or guarantee acceptance |

All business systems, policies, claims, brokers, payments, commissions, adjusters, and leads used in development or testing are synthetic or simulated.

---

## 3. Architecture principles

1. **AI First, not AI Only** — use the LLM for language understanding, classification, extraction, reasoning support, and response generation; keep critical business rules deterministic.
2. **The LLM is not the source of truth** — business facts must come from approved Tools, APIs, or governed data sources.
3. **Tool Calling for business action** — every business query or action must use a deterministic, versioned, testable, and auditable Tool.
4. **No direct database access from agents** — agents must never query or modify databases directly.
5. **Human-in-the-Loop** — sensitive, ambiguous, low-confidence, legal, financial, or coverage-related decisions must escalate to a person.
6. **Security and privacy by design** — use least privilege, managed identities, secure configuration, data minimization, and synthetic data outside production.
7. **Observability by design** — propagate a correlation ID through the API, supervisor, agents, Tools, workflows, and telemetry.
8. **RAG is documentary only** — RAG may retrieve manuals, procedures, conditions, FAQs, and other documents. Transactional status must use Tools.
9. **Resilience is explicit** — use timeouts, retries with backoff, idempotency, and circuit breakers where applicable.
10. **Architecture decisions are justified** — major decisions require an ADR with context, alternatives, consequences, risks, and review triggers.

---

## 4. Target architecture

### 4.1 Agent topology

- **Supervisor Agent**: single logical entry point; validates user context, classifies intent, applies guardrails, routes to a domain agent, maintains context, and escalates below the confidence threshold. It does not execute business logic.
- **Claims Agent**: uses approved claims Tools and delegates long-running processes to Durable Functions.
- **Broker Services Agent**: uses approved broker Tools and enforces broker-level authorization boundaries.
- **Commercial Intake Agent**: uses approved intake Tools and supports synthetic lead preregistration and routing.

New agents must:

1. Be created under `src/agents/`.
2. Implement the common agent contract.
3. Register only explicitly authorized Tools.
4. Define permitted and prohibited decisions.
5. Include unit, integration, and conversational tests.
6. Update architecture mapping, backlog, and sprint documentation.

### 4.2 Tool model

Tools are deterministic service operations implemented through `src/services/` and hosted, where appropriate, in Azure Functions.

Minimum reference Tools:

- Claims: `get_policy`, `validate_policy_status`, `get_payment_status`, `create_claim_notice`, `find_available_adjuster`, `assign_adjuster`, `send_claim_notification`.
- Broker Services: `get_broker_policies`, `get_procedure_status`, `get_receipts`, `get_commissions`, `create_commission_payment_request`, `create_support_ticket`.
- Commercial Intake: `classify_business_request`, `identify_insurance_line`, `validate_lead_information`, `create_lead_preregistration`, `upload_lead_document`, `assign_business_channel`, `generate_tracking_number`.

Every Tool must define purpose, authorized agent, input/output schema, validations, errors, timeout, retry, idempotency, audit event, sensitive-data classification, and tests.

### 4.3 Conversation and memory model

- Conversation history: Azure Cosmos DB for NoSQL.
- Partition key: `/userId`.
- Expected content: `userId`, `conversationId`, `messages`, `summary`, `status`, `currentAgent`, `metadata`, `feedback`, timestamps, and correlation references.
- Context strategy: recent turns in full plus a compressed summary of older turns.
- Core insurance truth must never be stored in Cosmos DB as authoritative policy, claim, payment, or commission data.
- Redis is not part of Sprint 0. Add it only when an ADR and measured performance requirement justify it.

### 4.4 RAG

- Documents: Azure Blob Storage.
- Retrieval: Azure AI Search when `enableRag=true`.
- Models: Azure OpenAI / Azure AI Foundry, subject to quota and approved deployments.
- RAG must provide source references and must not replace Tools for live business data.

### 4.5 Identity and security

- Frontend: Microsoft Entra ID with OAuth 2.0 / OIDC.
- Backend: token validation and role/scope checks.
- Service-to-service: Managed Identity.
- Secrets: Azure Key Vault.
- API governance: Azure API Management when enabled.
- No secrets in code, prompts, logs, pipeline YAML, `.env.example`, or documentation.

---

## 5. Technology stack

| Layer | Technology |
|---|---|
| Backend API | Python 3.12, FastAPI, Pydantic |
| Frontend | React, TypeScript |
| LLM platform | Azure OpenAI / Azure AI Foundry |
| Conversation store | Azure Cosmos DB for NoSQL |
| Document storage | Azure Blob Storage |
| RAG retrieval | Azure AI Search, optional |
| Deterministic Tools | Azure Functions |
| Long-running workflows | Azure Durable Functions |
| Container runtime | Azure Container Apps |
| Registry | Azure Container Registry |
| Secrets | Azure Key Vault |
| Workload identity | Managed Identity |
| Authentication | Microsoft Entra ID |
| IaC | Azure Bicep |
| CI/CD | Azure DevOps Pipelines |
| Observability | OpenTelemetry, Application Insights, Azure Monitor, Log Analytics |
| Backend quality | Ruff, mypy, pytest |
| Local runtime | Docker Compose |

Do not add AKS, Kubernetes, Helm, Terraform, Redis, another agent framework, or another database unless the current PBI explicitly requires it and an ADR justifies the change.

---

## 6. Repository structure

```text
vibecoding/
├── .vscode/
├── apps/
│   ├── api/src/
│   └── web/src/
├── artifacts/
├── configs/
│   ├── prompts/
│   └── security/
├── data/
│   ├── external/
│   ├── interim/
│   ├── processed/
│   └── raw/
├── docs/
│   ├── Architecture/
│   └── sprint_00/
├── models/
├── notebooks/
├── ops/
│   ├── bicep/
│   ├── docker/
│   ├── k8s/
│   └── scripts/
├── reports/
├── src/
│   ├── agents/
│   ├── common/
│   ├── config/
│   ├── core/
│   ├── dl/
│   ├── domain/
│   ├── ml/
│   ├── observability/
│   ├── pipelines/
│   ├── rag/
│   └── services/
├── tests/
│   ├── e2e/
│   ├── integration/
│   ├── unit/
│   └── conversational/
├── azure-pipelines.yml
├── CLAUDE.md
├── docker-compose.yml
└── README.md
```

Rules:

- Do not rename, delete, or move required top-level folders.
- Do not create a new top-level folder without approval.
- `apps/api/` contains the deployable FastAPI transport layer.
- `apps/web/` contains the deployable React application.
- `src/` is the reusable internal application and domain library.
- `src/core/` contains orchestration, routing, guardrails, permissions, resilience, and context management.
- `src/agents/` contains Supervisor and domain agents.
- `src/services/` contains Tool adapters and service abstractions.
- `src/domain/` contains domain models and contracts.
- `src/observability/` contains logging, tracing, metrics, and audit helpers.
- `src/rag/` contains retrieval logic only.
- `configs/prompts/` contains versioned prompts. Do not embed long system prompts directly in Python.
- `data/raw/` is read-only.
- `ops/k8s/` is retained only because it is part of the academic folder standard; it is reserved for future use.
- `docs/Architecture/` contains cross-sprint living architecture artifacts and ADRs.
- `docs/sprint_NN/` contains sprint-specific evidence.
- Reserved ML/DL folders must not be populated without a real requirement.

---

## 7. Working principles

- Prioritize correctness, security, maintainability, traceability, and minimal-risk changes.
- Make the smallest viable change that completes the current PBI.
- Do not refactor unrelated areas.
- Do not introduce dependencies or architectural patterns unless explicitly required.
- Preserve public contracts whenever possible.
- Use synthetic data only.
- State assumptions clearly.
- Never claim a feature, test, deployment, or command succeeded unless it was actually executed.
- Do not commit, push, or use destructive commands without explicit authorization.
- Once Azure DevOps CI/CD is operational (PBI-07-01), Claude Code does not perform routine
  Azure deployments — see §7.1. A genuine one-off manual deployment (e.g., an infrastructure-only
  investigation the user explicitly requests) remains possible only when the user explicitly
  authorizes that specific action; it is the exception, never the default path.

### 7.1 Delivery responsibility model (Azure DevOps CI/CD owns deployment, PBI-07-01)

`azure-pipelines.yml` is the single source of truth for build, test, security, and deployment
automation (CLAUDE.md §5's stack table: "CI/CD | Azure DevOps Pipelines"). Once it is
operational for a given change path, responsibilities split as follows:

**Claude Code responsibilities:**

- Implement code for the current PBI.
- Add or update unit tests for the change.
- Run targeted, fast local validation for changed areas only (focused `pytest`/`vitest`
  selections, `ruff`/`mypy` on touched files) — never a routine full-repository regression as
  a substitute for the pipeline's own Quality stage.
- Update documentation (sprint docs, ADRs, this file where applicable).
- Stop before deployment: do not routinely run `docker build`/`docker push`,
  `az containerapp update`, or `az deployment group create` as part of normal PBI delivery —
  that is `azure-pipelines.yml`'s job (Stages 3-6: Build, Infrastructure, Deploy DEV, Smoke
  Tests).

**Azure DevOps responsibilities (`azure-pipelines.yml`):**

- Full regression — the complete backend (`pytest`) and frontend (`vitest`) suites, not just
  changed areas.
- Security gates — dependency vulnerability scanning (`pip-audit`, `npm audit`), secret
  scanning (`detect-secrets`).
- Image build and push to the existing Azure Container Registry, with commit/build-traceable
  versioned tags (never `latest`).
- Bicep validation and DEV infrastructure deployment.
- DEV Container App deployment (image update only — no infrastructure recreation).
- Smoke tests against the real deployed DEV environment.
- Deployment evidence (a published summary artifact: image tags, revisions, test results).

**Exception handling:** an infrastructure-only condition external to this codebase (e.g., an
Azure subscription quota limitation) must never be allowed to silently mark unrelated
application delivery as failed — the pipeline's Infrastructure stage is deliberately isolated
from the Deploy/Smoke Test stages for exactly this reason (see `azure-pipelines.yml`'s own
`InfrastructureDeploy` stage comments and `docs/sprint_07/decisions.md`).

---

## 8. How to work in this repository

For each non-trivial task:

1. Identify the active Sprint, PBI, and acceptance criteria.
2. Read only relevant files.
3. Provide a concise implementation plan.
4. List files to create or modify.
5. Identify conflicts with the architecture or repository.
6. Implement only the current PBI.
7. Run the smallest relevant validation first.
8. Update sprint documentation.
9. Produce the mandatory PBI summary.
10. Stop and ask for the next PBI.

Do not execute multiple PBIs in one change unless explicitly instructed.

---

## 9. Code and configuration standards

### Python

- Python 3.12.
- Type hints for public functions.
- Pydantic models for external contracts.
- Async I/O for network operations where supported.
- No bare `except`.
- Ruff-compatible and mypy-compatible.
- Public functions and classes require concise docstrings.

### TypeScript

- Strict mode.
- No undocumented `any`.
- Separate API, authentication, state, and UI concerns.
- Never store secrets in browser code.

### Bicep

- Use `@description()` on parameters.
- Use validation decorators where applicable.
- Do not emit secret outputs.
- Parameterize environment-specific values.

### PowerShell

- `Set-StrictMode -Version Latest`.
- `$ErrorActionPreference = 'Stop'`.
- Validate parameters and return non-zero exit codes on failure.
- Destructive actions require confirmation.

### Prompts

- Store prompts under `configs/prompts/`.
- Include prompt name, version, purpose, allowed Tools, prohibited decisions, and change notes.
- Do not place business rules exclusively in prompts.
- Material prompt changes require tests and sprint documentation.

### Secrets

- Use `src/config/` as the single application configuration entry point.
- Use environment variables for non-secret runtime settings.
- Use Key Vault for secrets and Managed Identity in Azure.
- `.env` is local-only; commit only `.env.example` placeholders.
- Never log tokens, secrets, API keys, connection strings, or sensitive conversation content.

---

## 10. Observability and audit

Every request must be traceable through:

- `correlationId`
- `conversationId`
- privacy-safe user reference
- selected agent
- Tool calls
- workflow instance
- latency
- result status
- escalation status

Do not store hidden chain-of-thought. Store only decision category, confidence, selected agent, Tool name, redacted metadata, error category, audit event, and user-visible response references.

---

## 11. Testing and validation

Validation order:

1. Lint and type check touched files.
2. Focused unit tests.
3. Contract tests for Tool or API schema changes.
4. Integration tests when service wiring changes.
5. Conversational tests when prompts, routing, or agents change.
6. E2E tests when a complete business flow changes.
7. Infrastructure validation when Bicep or Azure wiring changes.

Requirements:

- New business logic requires unit tests.
- Every Tool requires contract tests.
- Every agent requires routing and prohibited-decision tests.
- Every prompt change requires conversational/evaluation tests.
- Coverage target: minimum 70% on implemented `src/` modules for the academic MVP.
- If validation cannot run, explain why and mark the PBI incomplete or conditionally complete.

---

## 12. Sprint documentation model

At the start of every sprint create:

`docs/sprint_NN/`

Use zero-padded numbers: `sprint_00`, `sprint_01`, and so on.

Every sprint folder must contain:

```text
docs/sprint_NN/
├── README.md
├── implementation-plan.md
├── validation.md
├── decisions.md
└── evidence/
```

Use `docs/Architecture/` only for living cross-sprint artifacts such as diagrams, ADRs, OpenAPI contracts, threat models, the data model, and traceability matrices.

### Sprint README template

```markdown
# Sprint NN — <Sprint name>

## Objective

## Scope

## Out of scope

## Deliverables

- [ ] PBI-NN: <title>

## Acceptance criteria

## Dependencies

## Risks

## Deliverable Log

## Sprint validation

## Sprint retrospective
```

At the end of every PBI:

1. Change only the relevant checkbox to `[x]`.
2. Append `PBI-NN: <short description> — <YYYY-MM-DD>` to the Deliverable Log.
3. Add evidence paths.
4. Update `validation.md` with commands actually executed and results.
5. Record deviations in `decisions.md`.
6. Do not erase previous entries.

A PBI is incomplete until these updates are done.

---

## 13. Deliverable completion rules

A PBI is complete only when:

1. Implementation is finished.
2. Acceptance criteria are met.
3. Relevant validation is completed.
4. Tests pass or exceptions are documented.
5. Sprint README is updated.
6. Validation evidence is recorded.
7. Architecture/ADR documentation is updated when applicable.
8. The mandatory PBI summary is produced.

Allowed statuses:

- `COMPLETE`
- `COMPLETE WITH CONDITIONS`
- `INCOMPLETE`

### Mandatory PBI summary

```markdown
### PBI-NN Summary

**Status:** COMPLETE | COMPLETE WITH CONDITIONS | INCOMPLETE

#### Files created or modified

| File | Purpose |
|---|---|

#### Acceptance criteria

| Criterion | Result | Evidence |
|---|---|---|

#### Validation performed

| Command or check | Result |
|---|---|

#### Architecture justification

- Requirement addressed:
- Principle or ADR:
- Why this component/change is needed:

#### Risks, blockers, and follow-ups

- ...

#### Sprint documentation updated

- `docs/sprint_NN/README.md`
- `docs/sprint_NN/validation.md`
```

---

## 14. Default sprint sequence

### Sprint 00 — Foundation and development controls

Repository, API/Web foundations, Docker, Bicep, ACR, Container Apps, Functions foundation, Cosmos DB conversation store, Key Vault, Managed Identity, Entra ID setup, observability, Azure DevOps CI/CD, Mock APIs, and synthetic-data foundation.

### Sprint 01 — Core multi-agent platform

Conversation API, context management, Cosmos repository, Supervisor Agent, intent classification, routing, guardrails, human escalation foundation, and Tool registry/contracts.

### Sprint 02 — Claims MVP

Claims Agent, claims Tools, Durable claim-notice workflow, synthetic policy/payment/adjuster APIs, folio, notification, and E2E claim scenario.

### Sprint 03 — Broker Services MVP

Broker Services Agent, authorization boundaries, policy/procedure/receipt/commission Tools, commission request workflow, and E2E scenarios.

### Sprint 04 — Commercial Intake MVP

Commercial Intake Agent, request classification, insurance-line identification, missing-information flow, lead preregistration, channel assignment, and E2E scenario.

### Sprint 05 — Hardening and final evidence

Security and prompt-injection testing, dashboards, cost telemetry, load/resilience tests, final documentation, academic evidence, and architecture review.

Do not start a later sprint unless the current sprint exit criteria are satisfied or the user explicitly accepts the risk.

---

## 15. Git and change management

- Work on one PBI at a time.
- Preferred branches:
  - `feature/pbi-NN-short-name`
  - `infra/pbi-NN-short-name`
  - `fix/pbi-NN-short-name`
- Do not commit generated secrets, `.env`, test credentials, build output, or private data.
- Do not commit automatically unless explicitly asked.
- Before suggesting a commit, show changed files, validation status, open risks, and a suggested message.
- Commit format: `type(scope): PBI-NN short description`.

---

## 16. Context and Claude Code session rules

- Read only files needed for the current PBI.
- Prefer targeted edits over complete rewrites.
- Do not repeat large file contents in responses.
- Use diffs or concise summaries.
- Use `/compact` after completing a PBI, before starting the next PBI, or after a long debugging session.
- Before compacting, ensure sprint documentation reflects the current state.

At the beginning of a new session:

1. Confirm repository root.
2. Identify active Sprint and PBI from `docs/sprint_NN/README.md`.
3. Read the current sprint README, current PBI prompt, and directly relevant files.
4. State the current PBI and short plan.
5. Do not restart completed work.

When resuming:

- Verify Git diff and sprint README before continuing.
- Repository files and sprint documentation are the source of truth, not conversation memory alone.

---

## 17. Definition of done

A task is done only when requested behavior is implemented, architecture principles remain satisfied, relevant validations have run, tests pass or exceptions are documented, no secrets or real sensitive data were introduced, sprint documentation is updated, and the PBI summary is produced.

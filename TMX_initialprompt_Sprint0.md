# TMX Enterprise AI Reference Platform — Sprint 0 Initial Prompt

You are acting as a Principal Azure Solutions Architect, Senior DevOps Engineer, Lead Software Architect, and Security Architect.

Your task is to implement **Sprint 0 — Foundation and Development Controls** for the **TMX Enterprise AI Reference Platform**.

The goal is to create a reproducible, secure, observable, and cost-conscious Azure foundation that can be deployed with a single command per environment and that supports the later implementation of:

- Web application.
- Orchestrator API.
- Supervisor Agent.
- Domain Agents.
- Deterministic Tools.
- Durable Workflows.
- Conversation history.
- Optional document RAG.

This is an academic reference implementation inspired by a corporate insurer. It is not an official TMX production architecture and must not include real internal systems, real credentials, real customer information, or undocumented organizational assumptions.

---

## 0. MANDATORY PREPARATION

Before creating or modifying any file:

1. Read `CLAUDE.md` completely.
2. Read the architecture document:
   `TMX_Enterprise_AI_Reference_Architecture_and_Delivery_Standard_V2.0.docx`
3. Inspect the existing repository structure.
4. Create `docs/Architecture/sprint_0/`.
5. Store all Sprint 0 documentation in that folder.
6. Produce an implementation plan listing:
   - Files to create.
   - Files to modify.
   - Dependencies.
   - Assumptions.
   - Risks.
7. Do not proceed when an existing file conflicts with this prompt. Report the conflict first.

The architecture document is the source of truth. If this prompt conflicts with the architecture document, follow the architecture document and document the deviation.

---

## 1. PROJECT CONTEXT

- Project name: `TMX Enterprise AI Reference Platform`
- Short resource prefix: `tmxai`
- Repository type: vibecoding monorepo
- Cloud: Microsoft Azure
- Environments:
  - `dev`: deployable now.
  - `staging`: parameterized, not deployed unless explicitly requested.
  - `prod`: parameterized, not deployed.
- Infrastructure as Code: Azure Bicep.
- CI/CD: Azure DevOps Pipelines.
- Backend: Python 3.12 + FastAPI.
- Frontend: React + TypeScript.
- Container platform: Azure Container Apps.
- Tool runtime: Azure Functions.
- Long-running workflows: Azure Durable Functions.
- Conversation store: Azure Cosmos DB for NoSQL.
- Secrets: Azure Key Vault.
- Workload authentication: Managed Identity.
- Observability: Log Analytics, Application Insights, OpenTelemetry.
- Container registry: Azure Container Registry.
- API governance: Azure API Management, parameterized and disabled by default in dev if cost or subscription constraints require it.
- RAG: optional. Azure Blob Storage + Azure AI Search only when enabled.
- Redis: optional and disabled by default. Do not deploy it unless an ADR and a measurable performance requirement justify it.

---

## 2. ARCHITECTURAL JUSTIFICATION RULE

Every Azure component and every major repository component must be documented with:

1. Business or technical need.
2. Requirement or architectural principle addressed.
3. Decision.
4. Alternatives considered.
5. Why the selected option is appropriate.
6. Risk introduced.
7. Mitigation.
8. Consequence if omitted.
9. Cost consideration.
10. Future review condition.

Create the document:

`docs/Architecture/sprint_0/component-justification.md`

At minimum, justify:

- Azure Container Apps.
- Azure Functions.
- Durable Functions.
- Azure Container Registry.
- Azure Key Vault.
- Managed Identity.
- Microsoft Entra ID application registration.
- Cosmos DB.
- Blob Storage.
- Log Analytics.
- Application Insights.
- API Management.
- Azure OpenAI / Azure AI Foundry integration.
- Azure AI Search when RAG is enabled.
- Bicep.
- Azure DevOps Pipelines.
- Docker.
- Mock APIs and synthetic data.
- Why AKS is not selected for the MVP.
- Why Redis is not selected for Sprint 0.

---

## 3. REQUIRED REPOSITORY STRUCTURE

Work exclusively inside the following structure. Do not rename or delete these folders. Do not create new top-level folders without explicit approval.

```text
vibecoding/
├── .vscode/
├── apps/
│   ├── api/
│   │   └── src/
│   └── web/
│       └── src/
├── artifacts/
├── configs/
├── data/
│   ├── external/
│   ├── interim/
│   ├── processed/
│   └── raw/
├── docs/
│   └── Architecture/
│       └── sprint_0/
├── models/
├── notebooks/
├── ops/
│   ├── bicep/
│   │   ├── main.bicep
│   │   ├── modules/
│   │   └── parameters/
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
│   └── unit/
├── azure-pipelines.yml
└── azure-pipelines/
    └── templates/
```

Rules:

- `ops/k8s/` must be retained because it belongs to the academic repository standard, but it remains reserved and unused in the MVP.
- Add `ops/k8s/README.md` explaining why Kubernetes is not used for this MVP and under what future conditions AKS could be reconsidered.
- Empty future folders must contain `.gitkeep` and a short `README.md` only when their purpose is not obvious.
- Do not create artificial code merely to fill reserved folders.

---

## 4. SPRINT 0 DELIVERABLES

### Deliverable 1 — Repository foundation

Create:

- `.gitignore`
- `.env.example`
- `README.md`
- `CLAUDE.md` only if it does not exist.
- `.vscode/settings.json`
- `.vscode/extensions.json`
- `ops/scripts/init_structure.ps1`

The initialization script must:

- Be idempotent.
- Create every required folder.
- Create `.gitkeep` files where necessary.
- Report created, existing, and failed paths.
- Never overwrite non-empty files.

The root README must include:

- Purpose.
- Academic/reference nature.
- Architecture summary.
- Repository map.
- Prerequisites.
- Local development.
- Infrastructure deployment.
- Testing.
- Security rules.
- Naming conventions.
- Decision log.
- Current Sprint 0 scope.
- Explicitly deferred items.

---

### Deliverable 2 — Minimal backend and frontend foundations

#### Backend — `apps/api`

Use:

- Python 3.12.
- FastAPI.
- Pydantic Settings.
- Uvicorn.
- pytest.
- Ruff.
- mypy.
- OpenTelemetry prepared but not connected to production credentials.

Create at minimum:

```text
apps/api/
├── Dockerfile
├── pyproject.toml
└── src/
    ├── main.py
    ├── api/
    │   ├── routes/
    │   │   ├── health.py
    │   │   └── version.py
    │   └── middleware/
    │       └── correlation_id.py
    ├── config/
    │   └── settings.py
    └── observability/
        └── logging.py
```

Endpoints:

- `GET /health`
- `GET /version`

Every response must include `X-Correlation-ID`.

Do not implement agents, business Tools, RAG, or real authentication during Sprint 0.

#### Frontend — `apps/web`

Create only a minimal React + TypeScript application foundation with:

- Dockerfile.
- Package manifest.
- Health-ready root page.
- Configuration placeholder for API URL.
- No real login implementation.
- No complete chat experience yet.

---

### Deliverable 3 — Docker local environment

Create:

- `docker-compose.yml`
- Backend Dockerfile.
- Frontend Dockerfile.

The compose file must start:

- API.
- Web.

Do not run local Cosmos DB or Redis containers unless explicitly justified. Use in-memory or mocked adapters for local Sprint 0 tests.

Required local checks:

- API responds at `/health`.
- Frontend loads.
- API correlation ID is returned.
- Docker builds are reproducible.

---

### Deliverable 4 — Azure Bicep IaC

Create:

```text
ops/bicep/
├── main.bicep
├── modules/
│   ├── log-analytics.bicep
│   ├── application-insights.bicep
│   ├── acr.bicep
│   ├── key-vault.bicep
│   ├── managed-identities.bicep
│   ├── storage.bicep
│   ├── cosmos-db.bicep
│   ├── container-apps-environment.bicep
│   ├── container-apps.bicep
│   ├── function-apps.bicep
│   ├── api-management.bicep
│   ├── ai-search.bicep
│   └── azure-openai-reference.bicep
└── parameters/
    ├── dev.bicepparam
    ├── staging.bicepparam
    └── prod.bicepparam
```

#### General Bicep rules

- `main.bicep` uses `targetScope = 'resourceGroup'`.
- Every parameter has `@description()`.
- Use validation decorators where applicable.
- No secrets in code or parameter files.
- Every resource receives standard tags:
  - `project`
  - `environment`
  - `managedBy`
  - `classification`
  - `costCenter` as a parameter, never a fabricated value.
- Resource names must be generated consistently from project prefix, resource type, environment, and uniqueness requirements.
- Use `uniqueString()` only where Azure requires globally unique names.
- No personal names or personal email addresses in resource names or tags.
- Public network access may be enabled for dev only through a parameter.
- Staging and production parameters must default to stricter network and security controls.
- Outputs must not expose secrets.

#### Required resources

1. Log Analytics Workspace.
2. Application Insights linked to Log Analytics.
3. Azure Container Registry:
   - admin user disabled.
   - anonymous pull disabled.
4. Key Vault:
   - RBAC authorization.
   - soft delete.
   - purge protection parameterized; enabled for staging/prod.
5. User-assigned Managed Identities for:
   - API.
   - Web if needed.
   - Function Apps.
6. Storage Account for:
   - Function runtime.
   - documents/artifacts.
7. Cosmos DB for NoSQL:
   - Serverless for dev.
   - Session consistency.
   - Database: `tmxai-conversation-db`.
   - Container: `conversations`.
   - Partition key: `/userId`.
   - TTL configurable.
   - Stores conversation history, conversation summaries, session state, agent/tool metadata, and user feedback.
   - Must not store policy, payment, claim, or other core business truth.
8. Azure Container Apps Environment.
9. Container Apps:
   - API.
   - Web.
   - Initially deployable with placeholder images or conditionally disabled until images exist.
10. Function App:
   - Foundation for deterministic Tools.
11. Durable Functions foundation:
   - Use the Function App model selected by the project.
12. API Management:
   - Controlled by `enableApiManagement`.
   - Disabled by default in dev when cost constraints apply.
13. Azure AI Search:
   - Controlled by `enableRag`.
   - Disabled by default.
14. Azure OpenAI:
   - Do not assume quota or deployment availability.
   - Accept an existing resource/deployment reference through parameters, or create the resource only when explicitly enabled and supported.
15. Redis:
   - Do not create a Redis module in Sprint 0.
   - Document the deferred decision and trigger conditions in an ADR.

#### Cosmos DB documentation requirement

Create:

`docs/Architecture/sprint_0/cosmos-conversation-store.md`

Include:

- Why Cosmos DB is used.
- Data model.
- Partition strategy.
- TTL strategy.
- Expected query patterns.
- PII handling.
- Retention.
- Cost risks.
- Why it is not the source of truth for insurance transactions.
- Alternative considered: PostgreSQL.
- Review triggers.

---

### Deliverable 5 — Entra ID application registration

Because Entra ID application registrations may require Microsoft Graph permissions and tenant-level privileges, do not assume Bicep alone can create them in every environment.

Create:

- `ops/scripts/configure-entra-apps.ps1`
- `docs/Architecture/sprint_0/entra-id-setup.md`

The script must:

- Support a dry-run mode.
- Create or update app registrations only when permissions exist.
- Define separate identities for web and API when appropriate.
- Configure redirect URIs through parameters.
- Configure scopes/roles through parameters.
- Never create or print client secrets unless explicitly requested.
- Prefer federated credentials or managed identity where applicable.
- Clearly identify manual approval steps.

---

### Deliverable 6 — Azure DevOps CI/CD

Create:

```text
azure-pipelines.yml
azure-pipelines/templates/
├── validate-infra.yml
├── test-backend.yml
├── test-frontend.yml
├── build-images.yml
├── push-acr.yml
├── deploy-infra.yml
├── deploy-container-apps.yml
├── deploy-functions.yml
└── smoke-tests.yml
```

Pipeline stages:

1. Validate:
   - Bicep build/lint.
   - Bicep what-if.
   - YAML validation.
   - Secret scanning.
   - Dependency scanning.
2. Test:
   - Backend tests.
   - Frontend tests.
   - Contract tests where available.
3. Build:
   - API image.
   - Web image.
4. Push:
   - Push immutable build tag.
   - Optional `latest` only for dev.
5. Deploy infrastructure:
   - Dev only by default.
6. Deploy applications:
   - Container Apps.
   - Functions.
7. Smoke tests:
   - API health.
   - Frontend availability.
   - Correlation ID.
8. Rollback:
   - Revert Container App revision on smoke-test failure.

Rules:

- PRs validate and test but do not deploy.
- `develop` may deploy dev.
- `main` requires approval and must not automatically deploy production.
- Use Azure DevOps service connections and workload identity federation where possible.
- Secrets must come from Key Vault or protected variable groups.
- Do not store secrets in YAML.

---

### Deliverable 7 — Infrastructure validation tests

Create:

```text
tests/integration/
├── conftest.py
└── test_infra.py
```

Use `pytest` and `DefaultAzureCredential`.

Tests must be safe, reversible, and skip clearly when optional resources are disabled.

Required tests:

1. Key Vault reachable.
2. ACR reachable.
3. Cosmos DB reachable.
4. Cosmos DB conversation CRUD:
   - Create a synthetic conversation item.
   - Read it.
   - Update summary/state.
   - Delete it.
5. Container Apps environment exists.
6. API Container App health endpoint responds when deployed.
7. Application Insights/Log Analytics resources exist.
8. Function App exists.
9. Optional API Management test when enabled.
10. Optional AI Search test when RAG is enabled.
11. Verify Redis is not required for Sprint 0.

Never require real business data.

---

### Deliverable 8 — Helper scripts

Create:

- `ops/scripts/deploy.ps1`
- `ops/scripts/validate_infra.py`
- `ops/scripts/destroy-dev.ps1`
- `ops/scripts/show-cost-resources.ps1`

`deploy.ps1` must:

- Accept `Environment`, `ResourceGroup`, `Location`, and parameter file.
- Fail fast if Azure CLI authentication is missing.
- Run Bicep validation and what-if.
- Request confirmation before deployment unless `-Force`.
- Deploy with a timestamped deployment name.
- Print non-secret outputs.
- Return a non-zero exit code on failure.

`validate_infra.py` must:

- Run infrastructure tests.
- Generate:
  `docs/Architecture/sprint_0/sprint0-validation.md`
- Include:
  - Test.
  - Status.
  - Duration.
  - Evidence.
  - Notes.

`destroy-dev.ps1` must:

- Work only for dev.
- Require explicit confirmation.
- Never target staging or production.
- Explain which resources will be deleted.

---

### Deliverable 9 — Architecture records and Sprint documentation

Create:

```text
docs/Architecture/sprint_0/
├── implementation-plan.md
├── component-justification.md
├── sprint0-architecture.md
├── sprint0-validation.md
├── cosmos-conversation-store.md
├── entra-id-setup.md
├── security-baseline.md
├── cost-considerations.md
├── deferred-decisions.md
└── adr/
    ├── ADR-001-container-apps-over-aks.md
    ├── ADR-002-cosmos-for-conversation-history.md
    ├── ADR-003-functions-for-tools.md
    ├── ADR-004-durable-functions-for-workflows.md
    ├── ADR-005-bicep-for-iac.md
    ├── ADR-006-redis-deferred.md
    └── ADR-007-rag-optional.md
```

Each ADR must include:

- Status.
- Context.
- Decision drivers.
- Alternatives.
- Decision.
- Justification.
- Positive consequences.
- Negative consequences.
- Risks.
- Review triggers.

---

## 5. CODING AND SECURITY STANDARDS

Apply to every file:

- Python:
  - Type hints.
  - Docstrings for public functions.
  - No bare `except`.
  - Ruff-compatible.
  - mypy-compatible.
- TypeScript:
  - Strict mode.
  - No `any` unless documented.
- Bicep:
  - Parameter descriptions.
  - Validation decorators.
  - No secret outputs.
- YAML:
  - 2-space indentation.
  - No secrets.
- PowerShell:
  - `Set-StrictMode -Version Latest`.
  - `$ErrorActionPreference = 'Stop'`.
  - Parameter validation.
- Docker:
  - Non-root user where practical.
  - Multi-stage builds.
  - Pinned major/minor runtime versions.
  - Health checks.
- Logging:
  - Structured.
  - Correlation ID.
  - No tokens, secrets, passwords, raw connection strings, or sensitive conversation content.
- Data:
  - Synthetic only.
  - No real policy, broker, claim, payment, or customer data.
- Configuration:
  - Environment-specific values through parameters or environment variables.
  - Secrets through Key Vault.
- Files:
  - Do not add personal names or emails to source headers.
  - Use project ownership roles rather than individuals.

---

## 6. EXECUTION ORDER

Execute in this order:

1. Inspect repository and report conflicts.
2. Create `docs/Architecture/sprint_0/implementation-plan.md`.
3. Initialize required folder structure.
4. Create repository foundation files.
5. Create minimal API and Web foundations.
6. Create Docker local environment.
7. Create complete Bicep modules and environment parameters.
8. Create Entra ID setup script and documentation.
9. Create Azure DevOps pipeline and templates.
10. Create infrastructure validation tests.
11. Create helper scripts.
12. Create ADRs and component justification.
13. Run all local validations.
14. Run Bicep build/lint.
15. Run Bicep what-if only if authenticated and the resource group exists.
16. Do not deploy Azure resources until explicit approval is given.

Do not stop and wait for separate Bicep specifications. Generate the complete Sprint 0 foundation from this prompt and the architecture document.

---

## 7. REQUIRED FINAL REPORT

At the end, provide:

1. Files created.
2. Files modified.
3. Commands executed.
4. Test results.
5. Bicep validation results.
6. Items skipped and why.
7. Assumptions.
8. Open decisions.
9. Estimated Azure cost drivers without inventing exact prices.
10. Security risks.
11. Manual actions required.
12. Readiness status:
    - Ready for dev deployment.
    - Ready with conditions.
    - Not ready.

Do not claim success for any command that was not actually executed.

---

## 8. DEFINITION OF DONE

Sprint 0 is complete only when:

- Repository structure is valid and documented.
- API and Web foundations build locally.
- Docker Compose runs both applications.
- Unit and integration tests pass or optional cloud tests are explicitly skipped.
- Bicep builds without errors.
- Dev, staging, and prod parameter files exist.
- Dev infrastructure can be deployed with one command.
- No secrets are stored in source control.
- Cosmos DB is explicitly justified as the conversation store.
- Cosmos DB is not used as the source of truth for core insurance data.
- Redis is documented as deferred, not silently omitted.
- Container Apps is justified against AKS.
- Every major component has an ADR or a documented justification.
- CI/CD validates, tests, builds, pushes, deploys, smoke-tests, and supports rollback.
- Sprint 0 validation evidence is generated.
- No production deployment occurs automatically.

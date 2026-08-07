# Sprint 00 — Foundation and Development Controls

## Objective

Establecer una base reproducible, segura, observable y desplegable para la plataforma multiagente.

## Scope

- Estructura del repositorio.
- API y Web mínimas.
- Docker.
- Bicep.
- Azure Container Registry.
- Azure Container Apps.
- Azure Functions y Durable Functions foundation.
- Cosmos DB para historial conversacional.
- Key Vault y Managed Identity.
- Entra ID setup.
- Observabilidad.
- Azure DevOps CI/CD.
- Datos sintéticos y Mock APIs base.

## Out of scope

- Supervisor Agent funcional.
- Claims Agent.
- Broker Services Agent.
- Commercial Intake Agent.
- RAG productivo.
- Integraciones con sistemas reales.
- Despliegue automático a producción.

## Deliverables

- [x] PBI-00-01: Inicializar y validar estructura del repositorio.
- [x] PBI-00-02: Crear API mínima con health, version y correlation ID.
- [x] PBI-00-03: Crear Web mínima y Docker Compose.
- [x] PBI-00-04: Crear Bicep base y parámetros por ambiente.
- [x] PBI-00-05: Crear Cosmos DB Conversation Store.
- [x] PBI-00-06: Crear Key Vault, Managed Identities y guía Entra ID.
- [ ] PBI-00-07: Crear pipeline CI/CD de Azure DevOps.
- [ ] PBI-00-08: Crear pruebas de infraestructura y scripts de validación.
- [ ] PBI-00-09: Consolidar ADRs, justificaciones y evidencia del sprint.

## Acceptance criteria

| ID | Criterion | Evidence expected |
|---|---|---|
| AC-01 | La estructura obligatoria existe y es reproducible | Ejecución de `init_structure.ps1` |
| AC-02 | API y Web construyen localmente | Logs y pruebas |
| AC-03 | Docker Compose inicia ambos servicios | Evidencia en `validation.md` |
| AC-04 | Bicep compila sin errores | Resultado de `az bicep build` |
| AC-05 | No existen secretos en el repositorio | Escaneo y revisión |
| AC-06 | Cosmos DB está justificado para conversaciones | ADR y documento de diseño |
| AC-07 | Container Apps está justificado frente a AKS | ADR |
| AC-08 | El pipeline valida, prueba, construye y prepara despliegue dev | YAML revisado |
| AC-09 | No se despliega producción automáticamente | Condiciones del pipeline |

## Dependencies

- Azure CLI.
- PowerShell 7 recomendado.
- Docker Desktop.
- Node.js.
- Python 3.12.
- Acceso a Claude Code.
- Suscripción Azure para pruebas de despliegue posteriores.

## Risks

| Risk | Probability | Impact | Mitigation |
|---|---:|---:|---|
| Falta de permisos Azure | Media | Alta | Validar con dry-run y documentar acciones manuales |
| Falta de cuota Azure OpenAI | Alta | Media | Referenciar recurso existente o mantener integración deshabilitada |
| Costos de APIM/AI Search | Media | Media | Flags de habilitación por ambiente |
| Inconsistencias entre arquitectura y código | Media | Alta | ADRs, trazabilidad y revisión por PBI |

## Deliverable Log

<!-- Append entries. Do not remove previous entries. -->

PBI-00-01: Repository structure and Starter Kit foundation files validated. Git installed and repository connected to GitHub (origin: https://github.com/jmarinme/enterprise-ai-multiagent-reference). `ops/scripts/init_structure.ps1` executed: 41/41 required directories existing, 0 created, 0 failures. All 8 Starter Kit foundation files present. No deviations. — 2026-08-05
Evidence: `docs/sprint_00/evidence/pbi-00-01-structure-validation.txt`

PBI-00-02: Minimal API foundation created (`apps/api`): FastAPI app with `GET /health`, `GET /version`, `X-Correlation-ID` middleware, structured JSON logging, Pydantic Settings, and a Dockerfile. 5/5 unit tests passed, ruff and mypy clean, live smoke test verified both endpoints and correlation-ID auto-generation/echo. Docker build not validated (Docker Desktop daemon not running locally; deferred to PBI-00-03). — 2026-08-06
Evidence: `docs/sprint_00/evidence/pbi-00-02-api-foundation-validation.txt`

PBI-00-03: Minimal Web application created (`apps/web`, React + TypeScript + Vite): chat-style layout with header (app name, API connectivity badge, API version), sidebar placeholder for conversation history, message area with synthetic welcome content, and an input+Send box (client-side only, canned placeholder reply — no real chat/agent processing). API client for `GET /health`/`GET /version`; responsive CSS. 7/7 unit tests passed, ESLint and `tsc --noEmit` clean, production build succeeded, runtime smoke test confirmed the built bundle correctly calls the running API. `docker-compose.yml` fixed (`VITE_API_URL` moved from a no-op runtime `environment` entry to a build-time `args` entry) and validated via `docker compose config`; actual `docker build`/`up` not validated (Docker Desktop daemon not running locally). — 2026-08-06
Evidence: `docs/sprint_00/evidence/pbi-00-03-web-docker-validation.txt`

PBI-00-04: Azure Bicep foundation created (`ops/bicep`): `main.bicep` orchestrating 8 reusable modules — Log Analytics, Application Insights (workspace-based), user-assigned Managed Identity, Key Vault (RBAC, foundation only), a Key Vault secret writer, Container Registry (admin user disabled, AcrPull via managed identity), a Container Apps (Consumption) environment, and one generic Container App module instantiated twice (API, Web). Fully parameterized (location, environment, naming, tags, image names/tags, scaling, CPU/memory); `dev`/`staging`/`prod` `.bicepparam` files with conservative dev scaling. No subscription/tenant/RG/secret/endpoint/image-tag values hardcoded. Cosmos DB, Azure OpenAI, AI Search, APIM, Storage, agents, and RAG kept out of scope. `az bicep build` clean (0 errors, 0 warnings) on `main.bicep` and all 8 modules; all 3 parameter files validated via `az bicep build-params`. No `az deployment create` executed — no Azure resources were deployed. — 2026-08-06
Evidence: `docs/sprint_00/evidence/pbi-00-04-bicep-foundation-validation.txt`

PBI-00-05: Cosmos DB Conversation Store foundation created. Infra: `ops/bicep/modules/cosmos-db.bicep` (single `conversations` container, partition key `/userId`, `disableLocalAuth: true`, Managed Identity granted the built-in Cosmos "Data Contributor" data-plane role, Serverless dev/staging, Provisioned 400 RU/s prod, TTL provisioned but inactive pending a retention ADR), wired into `main.bicep` and all 3 parameter files. Backend: typed `Conversation`/`Message` Pydantic models (camelCase wire format matching `CLAUDE.md` §4.3), a `ConversationRepository` Protocol, an in-memory adapter (default, no Azure required), and a Cosmos adapter authenticating via `DefaultAzureCredential` only (no keys/connection strings anywhere) — selected via a new `CONVERSATION_STORE_PROVIDER` setting. 11/11 unit tests passed locally with no Azure dependency; the Cosmos integration test scaffold correctly skips without `COSMOS_DB_ENDPOINT`. ruff and mypy clean (including the Cosmos adapter). `az bicep build` clean on the new module and `main.bicep`; all 3 parameter files validated. No Azure deployment performed. — 2026-08-06
Evidence: `docs/sprint_00/evidence/pbi-00-05-cosmos-conversation-store-validation.txt`

PBI-00-06: Key Vault and Managed Identity security foundation completed. Infra reviewed and confirmed already RBAC-only Key Vault, single shared Managed Identity, and minimum-role grants (AcrPull, Key Vault Secrets User, Cosmos Data Contributor) from PBI-00-04/05; Container Apps already authenticate via that identity. Added a `tenantId` output to `key-vault.bicep`/`main.bicep` for future pipeline use. Backend: `SecretProvider` Protocol + typed `SecretNotFoundError`, `EnvironmentSecretProvider` (default, local), `AzureKeyVaultSecretProvider` (`DefaultAzureCredential`, no keys), selected via a new `SECRET_PROVIDER` setting. No real secret values created — only a documented reserved-secret-name convention for future Azure OpenAI config. New `docs/sprint_00/security-baseline.md` documents local/Container-Apps/future-Azure-DevOps authentication and explicitly scopes out Entra ID end-user login. 21/21 new+existing unit tests passed (2 live-integration scaffolds correctly skipped), ruff and mypy clean. Two real issues found and fixed: a missing `aiohttp` transport dependency (also retrofitted into PBI-00-05's `cosmos` extra) and a `.gitignore` `secrets/` rule silently matching the new module directory (renamed to `secret_store/`). `az bicep build` clean; no Azure deployment performed. — 2026-08-07
Evidence: `docs/sprint_00/evidence/pbi-00-06-key-vault-managed-identity-validation.txt`

## Sprint validation

See `validation.md`.

## Sprint retrospective

Complete when closing the sprint:

- What worked:
- What did not:
- Technical debt:
- Security findings:
- Follow-up PBIs:

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

- [ ] PBI-00-01: Inicializar y validar estructura del repositorio.
- [x] PBI-00-02: Crear API mínima con health, version y correlation ID.
- [ ] PBI-00-03: Crear Web mínima y Docker Compose.
- [ ] PBI-00-04: Crear Bicep base y parámetros por ambiente.
- [ ] PBI-00-05: Crear Cosmos DB Conversation Store.
- [ ] PBI-00-06: Crear Key Vault, Managed Identities y guía Entra ID.
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

PBI-00-02: Minimal API foundation created (`apps/api`): FastAPI app with `GET /health`, `GET /version`, `X-Correlation-ID` middleware, structured JSON logging, Pydantic Settings, and a Dockerfile. 5/5 unit tests passed, ruff and mypy clean, live smoke test verified both endpoints and correlation-ID auto-generation/echo. Docker build not validated (Docker Desktop daemon not running locally; deferred to PBI-00-03). — 2026-08-06
Evidence: `docs/sprint_00/evidence/pbi-00-02-api-foundation-validation.txt`

## Sprint validation

See `validation.md`.

## Sprint retrospective

Complete when closing the sprint:

- What worked:
- What did not:
- Technical debt:
- Security findings:
- Follow-up PBIs:

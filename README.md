# TMX Enterprise AI Starter Kit

Starter kit para iniciar el proyecto académico **TMX Enterprise AI Reference Platform**
con una estructura reproducible, documentación por sprint y controles mínimos para
desarrollo asistido por IA.

> Este repositorio es una implementación académica de referencia. No representa una
> arquitectura productiva oficialmente aprobada y no debe contener datos, credenciales
> o nombres de sistemas internos reales.

## Contenido

- `CLAUDE.md`: reglas permanentes para Claude Code.
- `TMX_initialprompt_Sprint0.md`: prompt de ejecución del Sprint 00.
- `ops/scripts/init_structure.ps1`: crea y valida la estructura base.
- `docs/sprint_00/README.md`: control de PBIs y evidencias del Sprint 00.
- `docs/Architecture/`: arquitectura viva, ADRs, diagramas y contratos.
- `apps/`: aplicaciones desplegables.
- `src/`: librería interna de agentes, dominio, servicios y observabilidad.
- `ops/`: infraestructura, automatización y scripts.
- `tests/`: pruebas unitarias, integración, conversacionales y E2E.

## Primer uso

1. Descomprime este ZIP en una carpeta nueva.
2. Abre la carpeta raíz en Visual Studio Code.
3. Ejecuta:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
./ops/scripts/init_structure.ps1
```

4. Revisa:

```powershell
git status
```

5. Inicia Claude Code desde la raíz:

```powershell
claude
```

6. En Claude Code, verifica la memoria del proyecto:

```text
/memory
```

7. Inicia el Sprint 00 con:

```text
Lee CLAUDE.md, TMX_initialprompt_Sprint0.md,
docs/Architecture/TMX_Enterprise_AI_Reference_Architecture_and_Delivery_Standard_V2.0.docx
y docs/sprint_00/README.md.

Primero inspecciona el repositorio, valida la estructura y crea
docs/sprint_00/implementation-plan.md. No despliegues recursos Azure hasta mi aprobación.
```

## Flujo de trabajo recomendado

- Un PBI a la vez.
- Una rama por PBI.
- Actualizar `docs/sprint_NN/README.md` al cerrar cada PBI.
- Registrar comandos reales en `validation.md`.
- Crear o actualizar un ADR ante decisiones arquitectónicas relevantes.
- Usar `/compact` al cerrar un PBI o antes de iniciar el siguiente.
- Reanudar la sesión más reciente desde la misma carpeta con:

```powershell
claude --continue
```

## Alcance inicial

El Sprint 00 prepara:

- estructura del repositorio;
- API y Web mínimas;
- Docker;
- Azure Bicep;
- Container Apps;
- Azure Functions;
- Cosmos DB para historial conversacional;
- Key Vault y Managed Identity;
- observabilidad;
- Azure DevOps CI/CD;
- documentación y ADRs.

No implementa todavía los agentes funcionales.

## Funcionalidades

- Supervisor Agent: clasifica intención, aplica guardrails y enruta a un agente de dominio.
- Claims Agent: guía un flujo sintético de notificación de siniestro después de horario.
- Broker Services Agent: consultas sintéticas de póliza, procedimiento, recibo, referencia de
  pago y comisión.
- Commercial Intake Agent: clasifica solicitudes comerciales, identifica línea de negocio y
  preregistra un lead sintético.
- API conversacional (`POST /chat`, `GET /conversations`, `GET /conversations/{id}`) con
  historial persistido en Azure Cosmos DB.
- ✓ Microsoft Entra ID: inicio de sesión empresarial en la Web (`apps/web/`) y validación de
  token en la API (`apps/api/`).
- ✓ ReAct + Tool Calling: los tres agentes especialistas (Claims, Broker Services, Commercial
  Intake) razonan mediante un bucle acotado Reason → Action → Observation → Reason → ... →
  Final Answer (`src/core/tool_calling/orchestrator.py`) antes de responder — nunca se expone
  el razonamiento interno, solo la respuesta final.

## Arquitectura (visión general)

```text
Usuario → React SPA (MSAL React) → Microsoft Entra ID (OAuth2 Authorization Code + PKCE)
        → FastAPI API (validación JWT vía JWKS) → Supervisor Agent (enrutamiento determinista)
        → Claims Agent / Broker Services Agent / Commercial Intake Agent (ReAct: Reason → Action
          → Observation → ... → Final Answer) → Tool Layer (determinista)
        → Proveedores de datos sintéticos
```

Diagrama de flujo completo (autenticación + agentes + tools):
[docs/Architecture/diagrams/authentication-request-flow.md](docs/Architecture/diagrams/authentication-request-flow.md).
Detalle completo de la decisión de autenticación:
[ADR-0010 — Enterprise Authentication using Microsoft Entra ID](docs/Architecture/adr/0010-enterprise-authentication-entra-id.md).
Detalle completo del patrón de razonamiento agéntico:
[ADR-0011 — Adoption of ReAct Pattern for Tool-Orchestrated Reasoning](docs/Architecture/adr/0011-react-pattern-for-tool-orchestrated-reasoning.md).

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Backend API | Python 3.12, FastAPI, Pydantic |
| Frontend | React, TypeScript, MSAL React |
| Autenticación | Microsoft Entra ID (OAuth2 Authorization Code + PKCE) |
| Conversation store | Azure Cosmos DB for NoSQL |
| Tools deterministas | Azure Functions |
| Workflows de larga duración | Azure Durable Functions |
| Contenedores | Azure Container Apps, Azure Container Registry |
| Secretos | Azure Key Vault |
| Identidad de servicio | Managed Identity |
| IaC | Azure Bicep |
| CI/CD | Azure DevOps Pipelines |
| Observabilidad | OpenTelemetry, Application Insights, Azure Monitor |

Ver `CLAUDE.md` sección 5 para el stack completo y las restricciones de tecnología permitida.

## Seguridad y autenticación

La API y la Web están protegidas con **Microsoft Entra ID**:

- ✓ OAuth2 Authorization Code + PKCE (sin client secret en el navegador).
- ✓ MSAL React (`@azure/msal-browser`, `@azure/msal-react`) para el inicio de sesión y la
  adquisición de tokens en la Web.
- ✓ JWT Validation: la API valida firma, expiración, audiencia y emisor de cada token
  (`apps/api/src/api/auth/`).
- ✓ JWKS: las claves públicas de firma se obtienen y cachean desde el endpoint de
  descubrimiento de Microsoft Entra ID.
- ✓ Conversation Isolation: el historial de conversación se asocia exclusivamente a la
  identidad derivada del token validado (`tid:oid`), nunca a un identificador provisto por el
  cliente.
- ✓ Enterprise Authentication: soporta usuarios internos y externos mediante la autoridad
  `/common`.

Detalle de contexto, decisión, alternativas y consecuencias en
[ADR-0010](docs/Architecture/adr/0010-enterprise-authentication-entra-id.md).

## Patrones de IA Agéntica

**Patrón primario: ReAct + Tool Calling.** Cada agente especialista razona mediante un bucle
acotado — `src/core/tool_calling/orchestrator.py` — antes de responder:

- ✓ Reason → decide si necesita una herramienta o ya puede responder.
- ✓ Action → solicita una Tool determinista (nunca la ejecuta directamente).
- ✓ Observation → recibe el resultado real de la Tool.
- ✓ Repite Reason/Action/Observation solo lo necesario, acotado por `max_iterations`.
- ✓ Final Answer → única salida visible; el razonamiento interno nunca se expone ni se
  persiste (CLAUDE.md §10).

**Patrones complementarios ya implementados:** Multi-Agent (Supervisor + 3 agentes de dominio),
Planner–Executor (el Supervisor enruta de forma determinista, cada agente ejecuta), Memory
(memoria conversacional en Cosmos DB), Guardrails (Entra ID + validación JWT/JWKS + Tool Calling
determinista).

**Patrones futuros (no implementados):** LLM-as-a-Judge, Self-Reflection.

Detalle de contexto, decisión, alternativas y consecuencias en
[ADR-0011](docs/Architecture/adr/0011-react-pattern-for-tool-orchestrated-reasoning.md).

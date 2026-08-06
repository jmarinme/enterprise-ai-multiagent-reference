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

# TMX Enterprise AI Reference Platform — Administrator Guide

**Document version:** 1.0 — 2026-08-11 (PBI-10-04)
**Status:** Reflects the DEV environment as actually deployed and operated in this repository as of this date.

---

## 1. Purpose

### 1.1 Purpose

This guide describes how an administrator **operates** the TMX Enterprise AI Reference Platform
after it has already been deployed: how to check whether it is healthy, where to look when it
isn't, what configuration governs its runtime behavior, what monitoring and logging exist, and
what to do during an incident. It does not describe how to provision infrastructure or release a
new version — that process is documented in `Deployment_Guide.md`, which this guide references
rather than repeats.

### 1.2 Scope

In scope: day-to-day and incident-driven operation of the already-deployed DEV environment
(`rg-tmx-agent-platform-dev`) — monitoring, logging, configuration review, routine operational
commands, backup/recovery posture, incident response, and maintenance. Out of scope:
infrastructure provisioning, CI/CD pipeline mechanics, and application feature behavior (covered
respectively by `Deployment_Guide.md` and the ADRs under `docs/Architecture/adr/`).

### 1.3 Intended audience

An engineer or operator responsible for keeping the deployed platform running — not necessarily
the same person who built or deployed it. Assumes familiarity with Azure CLI and the Azure
Portal, but no prior exposure to this specific repository.

### 1.4 Administrator responsibilities

Per CLAUDE.md §10/§11 and the implemented monitoring/resilience surface described in this guide,
an administrator of this platform is responsible for:

- Confirming the platform is reachable and healthy (Section 3, Section 5).
- Reviewing structured logs and correlation IDs when investigating a reported problem (Section 6).
- Reviewing Azure Monitor alerts and acting on them (Section 5).
- Verifying that a given deployment actually took effect (Section 7; cross-references
  `Deployment_Guide.md` Section 9 for the automated smoke-test detail).
- Managing application-level configuration through the mechanisms this platform actually
  implements — Container App environment variables and, where enabled, Key Vault-backed secrets
  (Section 4) — never by editing source code for a runtime change.
- Diagnosing failures using the resilience mechanisms already built into the platform (retry,
  circuit breaker) rather than assuming every failure requires a code change (Section 9).
- This is an **academic reference platform using only synthetic data** (CLAUDE.md §1) — an
  administrator operating a derived, real production system must treat every "not implemented"
  callout in this guide as a gap to close first, not as an accepted risk to carry forward.

---

## 2. Platform Overview

Operational responsibilities only — see `Deployment_Guide.md` Section 2 for the build/deploy view
of the same components, and the ADRs cited below for design rationale.

| Component | Operational role |
|---|---|
| **Web Application** | The only end-user-facing surface. An administrator's concern here is reachability and correct API connectivity (CORS), not application logic. |
| **API (FastAPI)** | The single operational entry point for everything else — every Agent, Tool, and provider is reached through it. Its `/health` and `/ready` endpoints (Section 5) are the administrator's primary health signal. |
| **Supervisor Agent** | Routes every request to a domain Agent. Operationally invisible (no separate process/endpoint) — its behavior surfaces only through which Agent name appears in a `/chat` response and in logs. See [ADR-0007](adr/0007-ai-governance-boundary.md). |
| **Claims Agent** | Handles the synthetic after-hours claim flow. Operationally relevant because it is the one Agent with an alternate execution mode (`TOOL_PROVIDER`/`CLAIMS_WORKFLOW_PROVIDER`, Section 4) an administrator can select. |
| **Broker Services Agent** | Handles synthetic broker/commission queries. No administrator-facing configuration beyond the shared providers every Agent uses. |
| **Commercial Intake Agent** | Handles synthetic commercial lead intake. Same operational profile as Broker Services. |
| **Azure OpenAI** | The LLM backing every Agent's language understanding/response generation. An administrator's concern is availability and quota — a degraded Azure OpenAI dependency surfaces in `/ready` and in the resilience mechanisms of Section 9. |
| **Azure AI Search** | Provisioned but **not** the active `KnowledgeProvider` in DEV today (`knowledgeProvider=local` — see `Deployment_Guide.md` Section 8). An administrator should not expect RAG behavior to depend on this resource's health in the current environment. |
| **Cosmos DB** | Conversation history store. An administrator's concern is reachability (`/ready`) and the backup posture documented in Section 8 — not query performance tuning, which is out of scope for this academic-scale deployment. |
| **Azure Container Apps** | Hosts both applications. An administrator's primary operational surface: revision status, replica count, and logs (Section 7). |

---

## 3. Administration Responsibilities

Concrete, recurring activities implied by the platform's actual implemented surface (not a
generic operations checklist):

| Activity | How (this platform's actual mechanism) |
|---|---|
| Verify platform availability | `GET /health` (liveness) and `GET /ready` (dependency-aware readiness) — Section 5. |
| Review logs | Structured JSON logs via Log Analytics/Application Insights (Section 6) — no separate log-shipping step exists; Container Apps' own log destination already routes here. |
| Monitor services | Application Insights + the three provisioned metric alerts (error rate, latency, availability) — Section 5. |
| Validate deployments | Confirm the deployed image tag/revision matches the intended release (`az containerapp show` — Section 7); cross-reference `Deployment_Guide.md` Section 9 for the pipeline's own automated smoke tests. |
| Manage application configuration | Container App environment variables (`ops/bicep/main.bicep`'s `env` array) and, where `SECRET_PROVIDER=key_vault` is selected, Key Vault secrets — Section 4. |
| Review monitoring alerts | The `ag-tmxap-dev-ops` Action Group and its three metric alerts — Section 5. |
| Diagnose failures | Correlation-ID-driven log tracing (Section 6) plus the platform's built-in retry/circuit-breaker resilience (Section 9). |

---

## 4. Runtime Configuration

This is a **reference of what an administrator observes and can adjust in the already-deployed
environment** — for how these values get set during a deployment, see `Deployment_Guide.md`
Section 8. No secret value is reproduced anywhere in this guide.

### 4.1 Environment variables (API Container App)

Set directly on `apiContainerApp` (`ops/bicep/main.bicep`), visible via
`az containerapp show --name <api-app> --query "properties.template.containers[0].env"`:

| Variable | Purpose |
|---|---|
| `ENVIRONMENT`, `PROJECT_NAME` | Identify the running environment/project in logs and telemetry. |
| `LOG_LEVEL` | Root logging level for the structured JSON logger (`INFO` in DEV — Section 6). |
| `CORS_ALLOWED_ORIGINS` | The Web Container App's own FQDN, resolved at deploy time — never `"*"` (`docs/sprint_04/decisions.md`). If the Web app's origin ever appears to be blocked by CORS, this is the value to inspect first. |
| `AZURE_CLIENT_ID` | The user-assigned Managed Identity's client ID — required so `DefaultAzureCredential`'s managed-identity component knows which identity to use (a real deployment failure without it is documented in `docs/sprint_03/decisions.md`: "Unable to load the proper Managed Identity"). |
| `LLM_PROVIDER`, `KNOWLEDGE_PROVIDER`, `CONVERSATION_STORE_PROVIDER`, `TOOL_PROVIDER`, `CLAIMS_WORKFLOW_PROVIDER` | Select which concrete backend each provider abstraction uses. See [ADR-0006](adr/0006-provider-abstraction-pattern.md) and Section 4.4 below. |
| `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_MODEL_NAME`, `AZURE_OPENAI_API_VERSION`, `AZURE_OPENAI_USE_API_KEY` | Azure OpenAI connection target and auth mode. `AZURE_OPENAI_USE_API_KEY=false` in DEV — Managed Identity is the active auth path; no key is ever placed in this variable set. |
| `AZURE_AI_SEARCH_ENDPOINT`, `AZURE_AI_SEARCH_INDEX_NAME`, `AZURE_AI_SEARCH_USE_API_KEY` | Azure AI Search connection target — set even though `KNOWLEDGE_PROVIDER=local` means it is not currently read at runtime (Section 2). |
| `COSMOS_DB_ENDPOINT`, `COSMOS_DB_DATABASE`, `COSMOS_DB_CONTAINER` | Cosmos DB connection target. No connection string exists anywhere — `disableLocalAuth: true` on the account means key-based auth is impossible regardless (`ops/bicep/modules/cosmos-db.bicep`). |
| `AZURE_FUNCTIONS_BASE_URL`, `DURABLE_FUNCTIONS_BASE_URL` | The Claims Tool Layer/Durable Functions endpoint. Empty strings in DEV today (`deployServerlessToolLayer=false` — see [ADR-0003](adr/0003-azure-functions-tool-and-workflow-layer.md)); harmless because `TOOL_PROVIDER`/`CLAIMS_WORKFLOW_PROVIDER` are both `inprocess` and never read them. |

### 4.2 Managed Identity usage

A single, shared user-assigned Managed Identity (`id-tmxap-dev`) is used by both Container Apps
for every Azure-to-Azure call — Azure OpenAI (Cognitive Services OpenAI User), Azure AI Search
(Search Index Data Reader), Cosmos DB (Cosmos DB Built-in Data Contributor), Key Vault (Key Vault
Secrets User), and ACR (AcrPull). An administrator never manages a credential for any of these
calls — there is none to rotate or leak. The complete role assignment table is in
[ADR-0002](adr/0002-vnet-private-endpoints-hardening.md) §"RBAC audit." If a service call fails
with an authorization error, the first thing to check is whether the expected role assignment
still exists on the target resource for `id-tmxap-dev` (`az role assignment list --assignee
<managed-identity-principal-id>`), not a rotated key — none exists to rotate.

### 4.3 Key Vault integration

Key Vault (`ops/bicep/modules/key-vault.bicep`) is RBAC-authorized only (no access policies). It
currently holds exactly one secret in DEV: the Application Insights connection string
(`appinsights-connection-string`), injected into the API Container App as
`APPLICATIONINSIGHTS_CONNECTION_STRING` via a Container Apps `secretRef`
(`ops/bicep/main.bicep`'s `secretEnvMappings`). The `SecretProvider` abstraction
(`src/domain/secret_provider.py`) supports a Key Vault-backed implementation
(`AzureKeyVaultSecretProvider`, `src/services/secret_store/key_vault.py`) for any provider that
opts into API-key auth (`azure_openai_use_api_key`, `azure_ai_search_use_api_key`,
`azure_functions_use_key`, `durable_functions_use_key`) — **none of these opt-in flags are set to
true in DEV today**; every provider uses Managed Identity, not a Key Vault-retrieved key. An
administrator adding a new secret-backed configuration should add it to Key Vault via
`ops/bicep/modules/key-vault-secret.bicep` (Infrastructure change — out of this guide's scope,
see `Deployment_Guide.md`), never as a raw Container App environment variable.

### 4.4 Runtime providers (what an administrator can safely change vs. cannot)

Per [ADR-0006](adr/0006-provider-abstraction-pattern.md), every provider selection is a
configuration value, not a code path. An administrator can change any of the following via
`az containerapp update --set-env-vars` (a Container-App-level configuration change, distinct
from the image-update `az containerapp update --image` deployment operation described in
`Deployment_Guide.md` Section 7):

| Setting | Current DEV value | Safe to change without a code change? |
|---|---|---|
| `LLM_PROVIDER` | `azure_openai` | Yes — `mock`/`ollama` are valid alternatives, but changing to either in a live environment changes the platform's actual responses; treat as a real behavioral change, not a routine toggle. |
| `KNOWLEDGE_PROVIDER` | `local` | Not without also provisioning an AI Search index first — switching to `azure_ai_search` today would make `AzureAISearchProvider` fail at startup (`docs/sprint_03/decisions.md`), since no index has been built. |
| `TOOL_PROVIDER` / `CLAIMS_WORKFLOW_PROVIDER` | `inprocess` / `inprocess` | Not to `azure_functions`/`durable` — the Azure Functions Tool Layer is not deployed in DEV (`deployServerlessToolLayer=false`); flipping these without it would leave `AZURE_FUNCTIONS_BASE_URL` pointed at nothing. |
| `CONVERSATION_STORE_PROVIDER` | `cosmos` | No — switching to `in_memory` in a live environment would silently discard every future conversation on the next restart; this is a design-time choice, not an operational toggle. |

---

## 5. Monitoring

### 5.1 Application Insights

`ops/bicep/modules/app-insights.bicep` provisions `appi-tmxap-dev`, connected to the API
Container App via `APPLICATIONINSIGHTS_CONNECTION_STRING` (Section 4.3). This is the source of
the `requests/failed` and `requests/duration` metrics the alert rules below evaluate, and the
primary place to inspect request-level telemetry (status codes, durations, dependency calls) for
the API.

### 5.2 Log Analytics

`ops/bicep/modules/log-analytics.bicep` provisions the shared workspace
(`logAnalyticsRetentionInDays=30`, `logAnalyticsDailyQuotaGb=1` in DEV) that both Application
Insights and the Container Apps Environment write to. This is where an administrator runs
Kusto (KQL) queries over both application telemetry and Container Apps' own console log stream.

### 5.3 Azure Monitor — Action Group and Metric Alerts

Implemented in `ops/bicep/modules/monitor-alerts.bicep` (PBI-08-01, resolving Architecture
Review Finding A-11: "No alerting configuration... found anywhere... nothing appears wired to
notify a human on failure"). One Action Group and three metric alerts, all confirmed against this
platform's real, deployed resources (`az monitor metrics list-definitions`, per the module's own
header comment) — not guessed metric names:

| Alert | Metric | Condition | Severity |
|---|---|---|---|
| `alert-tmxap-dev-error-rate` | `requests/failed` (Application Insights) | More than 5 failed requests in a 5-minute window | 2 |
| `alert-tmxap-dev-high-latency` | `requests/duration` (Application Insights) | Average request duration above 3000ms in a 5-minute window | 2 |
| `alert-tmxap-dev-availability` | `Replicas` (the API Container App itself) | Fewer than 1 running replica, averaged over a 5-minute window | 1 (highest) |

All three fire into `ag-tmxap-dev-ops` (the Action Group). **The Action Group is created with
zero receivers by default** (`alertEmailAddress` defaults to an empty string in
`ops/bicep/main.bicep` — deliberately never defaulted to a placeholder address, per the module's
own parameter description). This means: **the alert rules exist and will fire and be visible in
the Azure Portal's Monitor → Alerts blade, but nobody is paged by email unless
`alertEmailAddress` has actually been set to a real operational address in the deployment
parameters.** An administrator should confirm this value before relying on alerting as an
unattended notification channel — check with
`az monitor action-group show --name ag-tmxap-dev-ops --resource-group
rg-tmx-agent-platform-dev --query "emailReceivers"`.

**No repository evidence exists of any of these three alerts having actually fired and been
observed during a real incident** — treat them as provisioned and correctly targeted (confirmed
live against real metric names), not as fire-drill-tested.

### 5.4 Health endpoints

Implemented in `apps/api/src/api/routes/health.py`:

- **`GET /health`** — unconditional liveness signal (`{"status": "ok"}`), never touches a
  downstream dependency, never fails. Suitable for a simple "is the process running" check.
- **`GET /ready`** — dependency-aware readiness. Concurrently checks every **configured**
  dependency (LLM, conversation store, knowledge provider — each check is skipped, reporting
  `"ok"`, if that provider's local/mock default is selected and there is nothing external to
  check) with a 5-second timeout per check. Returns HTTP `200 {"status": "ready", "checks":
  {...}}` when every configured dependency is reachable, or HTTP `503 {"status": "degraded",
  "checks": {...}}` naming exactly which dependency is unreachable otherwise. Never exposes a
  connection string, endpoint URL, API key, or raw exception message — only a per-dependency
  `ok`/`unreachable` word.

An administrator should use `/ready`, not `/health` alone, to distinguish "the process is up but
cannot actually serve a real request" from "the process is fully healthy" — this is exactly the
gap `/health` alone cannot see (the endpoint's own docstring, citing Architecture Review Finding
A-08).

### 5.5 Correlation IDs

`CorrelationIdMiddleware` (`apps/api/src/api/middleware/correlation_id.py`) reads the
`X-Correlation-ID` request header if present, or generates a new UUID if absent, stores it in a
`ContextVar` for the duration of the request, attaches it to `request.state.correlation_id`, and
echoes it back on the response's `X-Correlation-ID` header — always, regardless of success or
failure (`finally` block). Every structured log line emitted during that request automatically
carries the same `correlationId` field (Section 6). **Operational use**: when investigating a
specific reported problem, an administrator should ask for (or supply) the exact
`X-Correlation-ID` sent, then filter Log Analytics/Application Insights on that single value to
reconstruct the complete request path — no other correlation mechanism exists in this platform.

---

## 6. Logging

### 6.1 Application logs and structured logging

`configure_logging` (`apps/api/src/observability/logging.py`) replaces the default logging
handler with a single `JsonFormatter` writing single-line JSON to stdout — the format Container
Apps' own log collection expects for structured ingestion into Log Analytics. Every log line has
this shape:

```json
{"timestamp": "...", "level": "INFO", "logger": "...", "message": "...", "correlationId": "..."}
```

An `"exception"` field is added (formatted traceback text) whenever the log record carries
exception info. Root log level is controlled by the `LOG_LEVEL` environment variable (`INFO` in
DEV — Section 4.1).

### 6.2 Correlation IDs in logs

`CorrelationIdFilter` (same module) injects the current request's correlation ID (Section 5.5)
into every log record's `correlationId` field automatically — an administrator never needs to
manually thread a correlation ID through a log statement; any log line emitted anywhere during a
request already carries it via Python's `ContextVar` mechanism.

### 6.3 Error logging

Per CLAUDE.md §10, this platform does **not** log hidden chain-of-thought, prompt text, or raw
business/PII content — only decision category, tool name, correlation ID, redacted metadata, and
error category/status. Concretely: Tool and workflow activity logging
(`claims_tool_activity_start`/`_end`, `claims_activity_start`/`_end` —
[ADR-0003](adr/0003-azure-functions-tool-and-workflow-layer.md)) records `tool_name`/`activity`,
`correlation_id`, and a boolean `success` flag only. Readiness-check failures
(`apps/api/src/api/routes/health.py`) log a `"readiness_check_failed"` warning naming only the
failed dependency (`llm`/`conversation_store`/`knowledge_provider`), never the underlying
exception's message (deliberately caught and suppressed — the endpoint "must never itself raise/
crash," per its own inline comment). Resilience-layer retries
(`src/core/resilience/retry.py`) log a warning per retry attempt including the operation name,
attempt count, and the exception's string representation — this is the most detailed error
logging in the platform and is where an administrator should look first for a transient-failure
signature (Section 9).

### 6.4 How logs should be interpreted

- A `readiness_check_failed` warning for one specific dependency, without a corresponding spike
  in application errors, usually means that one dependency was transiently unreachable at the
  moment `/ready` was polled — check the resilience-layer retry logs for the same dependency in
  the same time window before assuming an outage.
- A retry-warning burst (`retry.py`'s `"%s failed on attempt %d/%d"` pattern) for one provider
  name, followed by a `"failed after %d attempt(s), giving up"` line, indicates that provider's
  circuit breaker likely just recorded a failure (Section 9) — search nearby logs for
  `CircuitBreakerOpenError` to confirm whether the breaker has since opened.
- Every log line's `correlationId` is the join key across the API, Supervisor, Agent, and Tool
  layers for a single request — always filter by it first when investigating one specific
  conversation, rather than scanning by timestamp alone.

---

## 7. Operational Procedures

Real command patterns, matching exactly what this platform's own pipeline and documented sprint
validation actually use (`azure-pipelines.yml`, `docs/sprint_*/validation.md`) — not generic Azure
guidance.

| Task | Command |
|---|---|
| Verify a Container App's current revision | `az containerapp show --name <api-app-or-web-app> --resource-group rg-tmx-agent-platform-dev --query "properties.latestRevisionName"` |
| Verify the deployed image tag | `az containerapp show --name <app> --resource-group rg-tmx-agent-platform-dev --query "properties.template.containers[0].image"` |
| List all revisions (including inactive ones) | `az containerapp revision list --name <app> --resource-group rg-tmx-agent-platform-dev` |
| Confirm application health | `curl -sf https://<api-fqdn>/health` and `curl -sf https://<api-fqdn>/ready` (Section 5.4) |
| Review failed deployments | Check the Azure DevOps pipeline's own `DeploymentSummary`/`SmokeTests` stage output (`Deployment_Guide.md` Section 9/11) — this repository's pipeline fails the run outright on any smoke-test assertion failure, so a failed deployment is visible in the pipeline's own result, not silently absorbed. |
| Restart a Container App (recover from a stuck/degraded instance without changing its image) | `az containerapp revision restart --name <app> --resource-group rg-tmx-agent-platform-dev --revision <revision-name>` — restarts the currently active revision in place; this is a distinct operation from redeploying a new image (`Deployment_Guide.md` Section 7.4/Section 10). |
| Check monitoring resources exist and are enabled | `az monitor metrics alert show --name alert-tmxap-dev-error-rate --resource-group rg-tmx-agent-platform-dev` (and the `-high-latency`/`-availability` equivalents); `az monitor action-group show --name ag-tmxap-dev-ops --resource-group rg-tmx-agent-platform-dev` |
| Confirm which Managed Identity role assignments exist | `az role assignment list --assignee <id-tmxap-dev-principal-id> --all` |

**Not implemented / not observed in this repository**: there is no documented procedure for
scaling replicas beyond the current `minReplicas=1`/`maxReplicas=1` (`dev.bicepparam`) — DEV runs
exactly one replica of each app by design (conservative-cost posture); changing replica counts is
an infrastructure (Bicep parameter) change, not a runtime operational action, and is out of this
guide's scope.

---

## 8. Backup and Recovery

Documented strictly as implemented — no disaster-recovery procedure is invented here.

### 8.1 What is implemented

- **Cosmos DB periodic backup** (`ops/bicep/modules/cosmos-db.bicep`): `backupPolicy.type:
  'Periodic'`, `backupIntervalInMinutes: 240` (every 4 hours), `backupRetentionIntervalInHours: 8`,
  `backupStorageRedundancy: 'Local'`. This is Cosmos DB's standard periodic backup mechanism — a
  point-in-time snapshot is retained for 8 hours after each backup interval. The module's own
  comment states this choice directly: "Periodic backup is Cosmos's cost-effective default,
  appropriate for this conservative dev/academic scope; Continuous backup was not requested and
  would add cost."
- **Container image history in ACR**: every previously-pushed image remains individually
  addressable by its commit-SHA-derived tag (never overwritten) — this is the mechanism
  `Deployment_Guide.md` Section 10 documents as the platform's actual rollback strategy for the
  *application* layer.
- **Container App revision retention**: a prior revision is not deleted when a new one activates
  (observed directly in `docs/sprint_08/decisions.md`) — a secondary, informal recovery point for
  application state, not a data backup.

### 8.2 What is NOT implemented (explicitly, not by omission)

- **No documented Cosmos DB restore procedure.** Periodic backup is enabled at the account level,
  but no runbook, script, or sprint record in this repository documents having ever performed
  (or tested) a restore-from-backup operation. An administrator needing to restore Cosmos DB data
  would be relying entirely on Azure's standard periodic-backup restore process (which requires
  opening an Azure Support request for periodic-mode accounts), not on any tooling this repository
  provides.
- **No continuous backup / point-in-time restore.** The Bicep module's own comment explicitly
  defers this: "Revisit via ADR if a future PBI needs point-in-time restore." No such ADR exists.
- **No backup for Key Vault, Azure AI Search, or Azure OpenAI configuration.** These are
  infrastructure-defined (Bicep) resources; their "backup" is the `ops/bicep/` source itself and
  its version-controlled history — there is no data-plane backup for them beyond that, and none is
  claimed.
- **No cross-region disaster recovery.** `isZoneRedundant: false` on the Cosmos DB account
  (`ops/bicep/modules/cosmos-db.bicep`), a single region for every resource, and no secondary
  region/failover configuration anywhere in `ops/bicep/`. This is consistent with
  [ADR-0001](adr/0001-networking-posture-and-vnet-deferral.md)'s and
  [ADR-0002](adr/0002-vnet-private-endpoints-hardening.md)'s conservative-cost DEV posture, not an
  oversight — but it means there is genuinely no DR capability to describe.

**Recommendation for a real production derivative of this platform**: define an explicit backup/
recovery ADR before go-live, covering at minimum Cosmos DB restore testing (not just backup
enablement) and a documented recovery time/point objective — none of this exists today.

---

## 9. Incident Management

How to respond to each failure mode, using only mechanisms actually implemented in this platform.

### 9.1 Application unavailable (API unreachable / `/health` failing)

1. Check `az containerapp revision list` — confirm at least one revision is `Active`/`Running`
   with `replicas >= 1`.
2. Check the `alert-tmxap-dev-availability` metric alert state (Section 5.3) — it is specifically
   designed to catch exactly this condition (`Replicas < 1` for 5 minutes).
3. Check recent deployment history — was a new image just deployed? If so, consider the rollback
   procedure in `Deployment_Guide.md` Section 10.
4. If the process is running but `/health` itself is failing, this indicates the FastAPI process
   itself is not serving requests at all (since `/health` never touches a downstream dependency)
   — check container logs (Section 6) for a startup-time crash.

### 9.2 Azure OpenAI failures

`AzureOpenAIProvider` (`src/llm/azure_openai_provider.py`) already wraps every call in the
platform's retry-with-backoff + circuit-breaker resilience layer
([ADR-0008](adr/0008-resilience-strategy.md)): transient failures are retried automatically (up
to 3 attempts, exponential backoff with jitter, 8s cap) before surfacing to the caller; a
sustained failure (5 consecutive failures) opens that provider's circuit breaker, which then
fails fast for 30 seconds before attempting one recovery trial call.

**Administrator action**: check `/ready`'s `"llm"` check first (Section 5.4) — `"unreachable"`
confirms the dependency, not a code defect, is the current problem. Check logs for
`CircuitBreakerOpenError` (Section 6.4) to determine whether the circuit is currently open (in
which case requests are failing fast, not retrying) or still closed (each request is individually
retrying and adding latency — also check the `alert-tmxap-dev-high-latency` alert). No manual
circuit-breaker reset exists or is needed — it self-recovers via the `HALF_OPEN` trial mechanism
once the underlying Azure OpenAI dependency recovers.

### 9.3 Cosmos DB failures

Same resilience pattern as Azure OpenAI, via `CosmosConversationRepository`
(`src/services/conversation_store/cosmos.py`) — retries only `408`/`429`/`500`/`503` status codes
(never `404`/`409`, which are legitimate outcomes, not transient failures), same
3-attempt/circuit-breaker composition. **Administrator action**: check `/ready`'s
`"conversationStore"` check; a sustained Cosmos outage will surface there before it surfaces as a
generic 500 error to end users, since `/ready` actively probes `list_conversations` against the
real account.

### 9.4 Azure AI Search failures

Same resilience pattern, via `AzureAISearchProvider` (`src/rag/azure_ai_search_provider.py`).
**Important operational note**: in DEV today, `KNOWLEDGE_PROVIDER=local` (Section 2), so
`AzureAISearchProvider` is not actually in the live request path — an Azure AI Search outage in
DEV as currently configured has **no effect on the running application**. This resilience layer
matters only in an environment where `KNOWLEDGE_PROVIDER=azure_ai_search` is actually selected.

### 9.5 Container App failures

If a specific revision is unhealthy (crash-looping, failing its own platform-level health probe),
`az containerapp revision restart` (Section 7) restarts it in place without a new image deploy.
If restarting does not resolve it, redeploying the last known-good image tag
(`Deployment_Guide.md` Section 10, Rollback Strategy) is the next step — there is no other
automated self-healing mechanism at the Container App level beyond what Azure Container Apps
itself provides natively (platform-level replica health probes).

### 9.6 What is NOT implemented

No automated incident alerting integration beyond the single email-based Action Group (Section
5.3) exists — no paging system (PagerDuty, Opsgenie, etc.), no Teams/Slack webhook, and no
runbook automation triggered by an alert. Incident response today is a manual process an
administrator performs using the tools and endpoints documented in this section.

---

## 10. Maintenance

Routine tasks implied by the platform's actual implemented tooling — not a generic maintenance
checklist.

| Task | Mechanism | Evidence |
|---|---|---|
| Dependency vulnerability review | `pip-audit` (Python) and `npm audit --omit=dev` (production JS) run automatically on every pipeline push (`SecurityScan` stage) | `azure-pipelines.yml`; `Deployment_Guide.md` Section 11.3 |
| Committed-secret review | `detect-secrets scan` runs automatically on every pipeline push | `azure-pipelines.yml` |
| Container image updates | Every `main` push rebuilds and redeploys the API image (and Web, when changed) — there is no separate "patch the base image" procedure documented beyond a normal code/dependency change flowing through the existing pipeline | `Deployment_Guide.md` Section 7 |
| Configuration review | Periodically compare the live Container App's `env` array (`az containerapp show ... --query "properties.template.containers[0].env"`) against `ops/bicep/main.bicep`'s declared `env` array — drift between the two indicates an out-of-band manual change was made and not captured in source control | `ops/bicep/main.bicep` |
| Monitoring review | Periodically confirm the three metric alerts are still `enabled: true` and that `alertEmailAddress` is still a real, monitored address (Section 5.3) | `ops/bicep/modules/monitor-alerts.bicep` |
| Resource cleanup | **Not implemented in this repository.** No script, pipeline stage, or documented procedure exists for pruning old ACR image tags, expired Cosmos backups, or stale Container App revisions. Azure's own default retention behavior applies (unbounded for ACR tags and Container App revisions unless a registry retention policy is separately configured — none is, in `ops/bicep/modules/container-registry.bicep`). |

**Not implemented**: there is no scheduled/automated maintenance job (e.g., a nightly pipeline run
purely for dependency-audit refresh) — every maintenance activity above runs only in response to a
code push or a manual administrator action.

---

## 11. Troubleshooting

Only problems with direct repository evidence of having actually occurred during development —
overlapping deployment-time issues already covered in `Deployment_Guide.md` Section 13 are not
repeated here; this table focuses on runtime/operational symptoms.

| Problem | Possible Cause | Resolution |
|---|---|---|
| `GET /ready` returns `503` with `"llm": "unreachable"` (or `conversationStore`/`knowledgeProvider`) | The corresponding external dependency (Azure OpenAI, Cosmos DB, or Azure AI Search) is transiently or persistently unreachable, or its Managed Identity role assignment was removed | Confirm via Section 9.2/9.3/9.4's per-dependency guidance; check the role assignment still exists (Section 4.2) before assuming a service-side outage |
| API Container App fails to start after a configuration change, citing "Unable to load the proper Managed Identity" | `AZURE_CLIENT_ID` env var missing or incorrect — `DefaultAzureCredential` cannot disambiguate which user-assigned identity to use | Confirm `AZURE_CLIENT_ID` matches `id-tmxap-dev`'s actual client ID (`docs/sprint_03/decisions.md` documents this exact failure during initial deployment) |
| Web frontend cannot call the API (CORS error in browser console) | `CORS_ALLOWED_ORIGINS` on the API Container App does not match the Web Container App's actual current FQDN (e.g., after an independent Web redeploy changed its host) | Verify `CORS_ALLOWED_ORIGINS` (Section 4.1) against the Web app's live FQDN; this value is normally resolved automatically by Bicep at deploy time, so a mismatch usually indicates an out-of-band manual change |
| `AzureOpenAIProvider`/`CosmosConversationRepository` import errors at container startup | The corresponding Azure SDK package was not installed in the API image despite the relevant provider being selected | Not an operational fix — requires a `Deployment_Guide.md`-scoped image rebuild with the correct dependency; see `Deployment_Guide.md` Section 13 for the original occurrence |
| A generic (non-domain) chat message routes to `FallbackAgent` instead of a specific Agent | Expected behavior — `RuleBasedIntentResolver` deterministically classifies messages with no recognized domain keyword as `UNKNOWN` | Not a defect; confirm the test/reported message actually contains a domain-relevant keyword if a specific Agent response was expected. See [ADR-0007](adr/0007-ai-governance-boundary.md) |
| Alerts are visible as "fired" in the Azure Portal but no one was notified | `alertEmailAddress` was left at its default empty string — the Action Group has zero receivers | Set a real operational email address in the deployment parameters and redeploy the `monitorAlerts` module (an infrastructure change — see `Deployment_Guide.md`) |

---

## 12. Operational Best Practices

Recommendations grounded in what this platform's implementation already assumes or enables —
not generic industry advice unrelated to this codebase:

- **Always filter by correlation ID first** (Section 5.5/6.4) when investigating a specific
  reported problem — it is the only cross-layer join key this platform provides, and every log
  line already carries it automatically.
- **Treat `/ready`, not `/health`, as the authoritative health signal** for anything beyond "is
  the process alive" — `/health` is deliberately blind to dependency health by design.
- **Never store a secret in a Container App environment variable directly.** Every current secret
  need in this platform is either avoided entirely (Managed Identity) or routed through Key Vault
  (Section 4.3) — a new configuration need that requires a real secret should follow the same
  pattern, not introduce a plaintext env var.
- **Treat a circuit-breaker-open condition as a signal to check the downstream dependency, not
  the application code** — [ADR-0008](adr/0008-resilience-strategy.md)'s whole design intent is
  that a tripped breaker means "the dependency is unhealthy," and the breaker self-recovers once
  it is.
- **Confirm `alertEmailAddress` is set to a real, monitored address** before relying on this
  platform's alerting as an unattended notification channel — it is not set by default (Section
  5.3).
- **Do not enable `KNOWLEDGE_PROVIDER=azure_ai_search` without first provisioning and populating
  a real AI Search index** — the provider will fail at startup otherwise (Section 4.4).
- **Do not enable `TOOL_PROVIDER=azure_functions`/`CLAIMS_WORKFLOW_PROVIDER=durable` while
  `deployServerlessToolLayer=false`** — there is no Azure Functions endpoint deployed for either
  to call (Section 4.4; [ADR-0003](adr/0003-azure-functions-tool-and-workflow-layer.md)).
- **Before adapting this platform for a real production workload**, close the gaps this guide
  explicitly flags as not implemented: a tested Cosmos DB restore procedure, a broader incident
  notification channel than a single email Action Group, and (per
  [ADR-0007](adr/0007-ai-governance-boundary.md)'s own framing and Section 1.4 above) full review
  of every academic-scope simplification against real operational requirements.

---

## 13. Administrator Checklist

A concise, recurring operational checklist using only the mechanisms documented above.

- [ ] `GET /health` returns `200 {"status": "ok"}`.
- [ ] `GET /ready` returns `200 {"status": "ready"}` with every configured dependency `"ok"`.
- [ ] `az containerapp revision list` shows the expected revision `Active` with `replicas >= 1`
      for both the API and Web Container Apps.
- [ ] Deployed image tag (`az containerapp show ... --query
      "properties.template.containers[0].image"`) matches the intended release.
- [ ] The three metric alerts (`error-rate`, `high-latency`, `availability`) are `enabled: true`.
- [ ] `ag-tmxap-dev-ops` has a real, monitored email receiver configured (not the empty default).
- [ ] No unexpected `CircuitBreakerOpenError` entries in recent logs for any of the three
      resilience-wrapped providers (Azure OpenAI, Cosmos DB, Azure AI Search).
- [ ] No unexplained drift between the live Container App `env` array and `ops/bicep/main.bicep`'s
      declared values.
- [ ] `id-tmxap-dev`'s role assignments on Azure OpenAI, Azure AI Search, Cosmos DB, Key Vault,
      and ACR are all still present (`az role assignment list --assignee <principal-id>`).
- [ ] Cosmos DB's periodic backup policy is still `enabled`/unchanged (`az cosmosdb show`).
- [ ] Recent pipeline runs (if any) show `SmokeTests`/`DeploymentSummary` succeeded — see
      `Deployment_Guide.md` Section 9 for what each smoke test actually validates.

---

## Cross-references

- `Deployment_Guide.md` — infrastructure provisioning, application build/release, CI/CD pipeline,
  and rollback procedure (not repeated in this guide).
- [ADR-0001](adr/0001-networking-posture-and-vnet-deferral.md) — Networking posture
- [ADR-0002](adr/0002-vnet-private-endpoints-hardening.md) — VNet/Private Endpoints hardening, RBAC audit
- [ADR-0003](adr/0003-azure-functions-tool-and-workflow-layer.md) — Azure Functions Tool Layer
- [ADR-0004](adr/0004-conversation-store-selection.md) — Conversation store selection
- [ADR-0005](adr/0005-application-hosting-strategy.md) — Application hosting strategy
- [ADR-0006](adr/0006-provider-abstraction-pattern.md) — Provider abstraction pattern
- [ADR-0007](adr/0007-ai-governance-boundary.md) — AI governance boundary
- [ADR-0008](adr/0008-resilience-strategy.md) — Resilience strategy
- [ADR-0009](adr/0009-conversation-memory-strategy.md) — Conversation memory strategy

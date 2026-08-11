# ADR-0005: Application Hosting Strategy — Azure Container Apps

## Status

Accepted — retroactively documented 2026-08-10 (PBI-10-02). This decision has been implemented
since Sprint 00/Sprint 01 (`ops/bicep/modules/container-app.bicep`,
`ops/bicep/modules/container-apps-environment.bicep`) and is codified in CLAUDE.md §5. This ADR
closes `docs/sprint_00/README.md` acceptance criterion AC-07 ("Container Apps está justificado
frente a AKS → ADR"), which was never satisfied by a dedicated document until now. Complements
[ADR-0003](0003-azure-functions-tool-and-workflow-layer.md), which covers the separate hosting
decision for the deterministic Tool Layer (Azure Functions), not the API/Web applications this
ADR covers.

## Context

The platform needs a container-hosting runtime for two deployable applications
(`apps/api/` — FastAPI transport layer, `apps/web/` — React frontend), per CLAUDE.md §6. Both are
already containerized (`apps/api/Dockerfile`, `apps/web/`'s own Dockerfile) and pushed to Azure
Container Registry (`ops/bicep/modules/container-registry.bicep`). This ADR records why Azure
Container Apps was chosen as the runtime that runs those images, as opposed to the alternatives
CLAUDE.md's stack table implicitly rules out.

## Problem

Which Azure compute platform should host the containerized API and Web applications, and is that
choice justified against real alternatives — specifically AKS/Kubernetes, which CLAUDE.md §5
excludes by name ("Do not add AKS, Kubernetes, Helm... unless the current PBI explicitly requires
it") but never explains?

## Decision

Use **Azure Container Apps** for both deployable applications.

- `ops/bicep/modules/container-apps-environment.bicep`: one shared Consumption-plan Container
  Apps Environment.
- `ops/bicep/modules/container-app.bicep`: one reusable module, instantiated twice in
  `ops/bicep/main.bicep` — `module apiContainerApp` and `module webContainerApp` — each pulling
  its image from the shared Azure Container Registry via the platform's shared Managed Identity
  (`AcrPull` role, [ADR-0002](0002-vnet-private-endpoints-hardening.md)'s RBAC audit table).
- Scale-to-zero/consumption-based billing, matching the platform's conservative-cost posture
  (the same posture applied to AI Search Free tier and Cosmos DB serverless —
  [ADR-0004](0004-conversation-store-selection.md)).
- Deployment is image-tag-only in steady state (CLAUDE.md §7.1: Azure DevOps updates the running
  revision via `az containerapp update`, never a Bicep redeploy for an application-only release).

## Why Container Apps

- **Right-sized for two stateless HTTP services.** Both `apps/api` and `apps/web` are ordinary
  containerized HTTP applications with no requirement for custom scheduling, DaemonSets,
  StatefulSets, or multi-container Pod sidecars — the class of problem Kubernetes exists to
  solve. Container Apps provides the operationally-relevant subset (revisions, HTTP-based
  autoscaling including scale-to-zero, ingress, Managed Identity, Dapr if ever needed) without
  cluster lifecycle management.
- **No cluster to operate.** There is no control plane, node pool, OS patching, or CNI/networking
  layer for this project to own — Microsoft manages all of it. This matches CLAUDE.md's academic/
  reference-platform framing (§1: "provide a reusable reference for future enterprise AI
  developments") better than a from-scratch Kubernetes deployment would, which would shift
  significant scope onto infrastructure operations rather than the multi-agent platform itself.
- **Native fit with the rest of the stack.** The same Managed Identity, the same Key Vault
  integration pattern, and the same VNet/Private Endpoint model
  ([ADR-0001](0001-networking-posture-and-vnet-deferral.md),
  [ADR-0002](0002-vnet-private-endpoints-hardening.md)) apply uniformly to Container Apps,
  Functions ([ADR-0003](0003-azure-functions-tool-and-workflow-layer.md)), and every other
  resource in `ops/bicep/` — one identity and network model across the whole platform, not a
  Kubernetes-specific identity/secrets layer (e.g., Workload Identity Federation, K8s Secrets)
  running alongside Azure's own.
- **Consumption-based cost model.** Scale-to-zero when idle is a direct cost fit for an academic
  demo with intermittent, low-volume traffic — a Kubernetes node pool bills for provisioned VM
  capacity regardless of traffic.

## Why not AKS

Rejected for this platform's actual requirements, not as a blanket judgment on Kubernetes:

- **No requirement calls for it.** Neither `apps/api` nor `apps/web` needs custom schedulers,
  privileged workloads, DaemonSets, service mesh beyond simple HTTP routing, or multi-tenant
  cluster isolation — the class of problem that justifies AKS's operational cost.
- **Operational overhead is disproportionate to the workload.** AKS requires managing node pools,
  cluster upgrades, CNI/networking configuration, and Kubernetes-native secret/identity wiring —
  none of which this platform's two stateless HTTP services need, and all of which would consume
  project effort better spent on the multi-agent domain logic CLAUDE.md's §1 goals actually
  target.
- **CLAUDE.md §5 explicitly names this exclusion** ("Do not add AKS, Kubernetes, Helm... unless
  the current PBI explicitly requires it and an ADR justifies the change") — no PBI to date has
  required it, and `ops/k8s/` in the repository structure is explicitly reserved but
  intentionally unpopulated (CLAUDE.md §6: "retained only because it is part of the academic
  folder standard... reserved for future use").

## Why not App Service

Rejected as the direct alternative within the same "no cluster to manage" tier:

- **Weaker multi-container/revision model.** Container Apps' revision-based deployment (multiple
  active revisions, traffic-split-capable, each independently addressable) fits a platform
  iterating through many PBIs with a need for safe, reversible releases better than classic App
  Service's single-slot-swap model.
- **App Service Plan quota is a proven blocker in this subscription.** PBI-06-01/06-01A
  established, via 3 independent real deployment attempts (`Y1`, `B1`, `P0v4`), that this
  subscription has zero deployable `Microsoft.Web` App Service quota in every region tried (see
  [ADR-0003](0003-azure-functions-tool-and-workflow-layer.md)'s full evidence chain). Container
  Apps runs on `Microsoft.App`, a distinct resource provider unaffected by that quota exhaustion
  — the API and Web Container Apps have deployed and run successfully throughout the same period
  Azure Functions could not.
- **Native Dapr/microservices-oriented features** (service-to-service invocation, pub/sub,
  bindings) that Container Apps offers over App Service are not used by this platform today, but
  keep the platform's compute layer aligned should a future PBI need lightweight service mesh
  capability without adopting AKS.

## Relationship with Azure Functions

Azure Container Apps (`Microsoft.App`) and Azure Functions (`Microsoft.Web`) are two distinct,
deliberately separate compute layers in this platform, not competing choices for the same
problem:

- **Container Apps** hosts the always-on, stateless HTTP applications: the FastAPI transport
  layer (`apps/api`) and the React frontend (`apps/web`).
- **Azure Functions** hosts the deterministic Tool Layer and Durable Functions workflow engine
  (`ops/functions/claims_tools/`) — event/HTTP-triggered, short-lived executions, per
  [ADR-0003](0003-azure-functions-tool-and-workflow-layer.md). This is a resource-provider-level
  separation (`Microsoft.Web`), which is precisely why the App Service quota exhaustion documented
  in ADR-0003 affects only the Functions layer and never the Container Apps layer this ADR
  covers — the two are provisioned, quota-gated, and scaled completely independently.

Both share the same Managed Identity, the same Key Vault secret, and (when
`enablePrivateNetworking=true`) the same VNet posture — the platform has one identity/network
model spanning both compute layers, not two parallel ones.

## Current DEV implementation

- `apiContainerApp` and `webContainerApp` (`ops/bicep/main.bicep`) are deployed and running in
  `rg-tmx-agent-platform-dev` today, reachable via each Container App's own
  `*.azurecontainerapps.io` FQDN (Container Apps Environment ingress, not VNet-internal — see
  [ADR-0002](0002-vnet-private-endpoints-hardening.md)'s `containerAppsEnvironmentInternal`
  discussion).
- `containerAppsEnvironmentInternal` defaults to `false` in every environment today (including
  staging/prod parameters), since no Front Door/Application Gateway exists yet — a Container
  Apps-specific consequence already recorded in ADR-0002, not repeated here.
- Deployment in steady state is CI/CD-owned (CLAUDE.md §7.1): Azure DevOps builds the image,
  pushes to ACR with a commit-traceable tag, and updates the Container App's active revision.
  Bicep-level changes to the Container App module itself remain infrequent, reviewed
  infrastructure changes, not part of routine PBI delivery.

## Future serverless option

Container Apps itself already supports a serverless consumption profile (scale-to-zero,
per-second billing) — the platform is not choosing between "serverless" and "not serverless" at
the application-hosting layer; it already has scale-to-zero today. What remains a genuinely open,
tracked question is the Tool Layer's own serverless hosting tier
([ADR-0003](0003-azure-functions-tool-and-workflow-layer.md)'s "Review triggers": Flex
Consumption, Elastic Premium, or Consumption for Azure Functions, once App Service quota is
granted) — a separate decision from this ADR's scope.

## Alternatives considered

- **AKS/Kubernetes.** Rejected — see "Why not AKS" above.
- **Azure App Service (Web Apps for Containers).** Rejected — see "Why not App Service" above.
- **Azure Virtual Machines / VM Scale Sets.** Rejected outright without deep analysis: fully
  unmanaged compute (OS patching, scaling logic, load balancing all hand-built) is a strictly
  worse fit than any PaaS/container-native option for two stateless HTTP services, and CLAUDE.md's
  stack table never names VMs as a candidate.
- **Azure Kubernetes Service Automatic / other managed-Kubernetes variants.** Considered
  implicitly under "AKS" above — even a managed-control-plane Kubernetes variant still imposes
  Kubernetes-native manifests, Helm, and cluster-scoped concepts CLAUDE.md §5 excludes, for no
  compensating benefit this platform's workload needs today.

## Consequences

- Positive: minimal operational surface for two ordinary HTTP services; consistent identity/
  network model shared with every other Azure resource in the platform; consumption billing fits
  the academic workload; revision-based deployment supports safe, CI/CD-driven releases.
- Negative / accepted trade-off: Container Apps offers less fine-grained scheduling control than
  Kubernetes (no custom schedulers, no DaemonSets) — accepted because no current or foreseeable
  PBI needs that control, and CLAUDE.md §5 explicitly reserves the option to introduce Kubernetes
  later if a real requirement and its own ADR justify it.
- The `ops/k8s/` folder remains reserved-but-empty per CLAUDE.md §6 — this ADR is the record of
  why it stays that way today, so a future contributor does not need to re-derive the reasoning.

## Review triggers

- If a future PBI introduces a workload requiring Kubernetes-specific primitives (custom
  schedulers, DaemonSets, StatefulSets, service mesh beyond Container Apps' Dapr integration) —
  revisit with its own ADR, per CLAUDE.md §5's own escape hatch.
- If Azure App Service quota is ever granted in this subscription and a future PBI proposes
  consolidating the Tool Layer onto the same compute model as the API/Web apps — that would be a
  distinct decision from this ADR, requiring its own justification against
  [ADR-0003](0003-azure-functions-tool-and-workflow-layer.md).
- If traffic/latency/cost characteristics change materially from the current low-volume synthetic
  workload this ADR's reasoning assumes.

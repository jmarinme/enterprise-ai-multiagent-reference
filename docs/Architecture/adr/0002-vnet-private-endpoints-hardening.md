# ADR-0002: VNet, Private Endpoints, and Network Hardening

## Status

Accepted — 2026-08-07 (PBI-03-04)

## Context

ADR-0001 (PBI-03-02) documented an all-public-network-access, RBAC-only posture and explicitly
named what production hardening would require: VNet-integrating the Container Apps Environment,
Private Endpoints for the four data-plane services, subnet separation, and Network Security
Groups. PBI-03-04 is that named follow-up. Per its own instructions, it implements exactly that
scope and explicitly does **not** implement Application Gateway, Azure Firewall, a DDoS
Protection Plan, WAF, hub-spoke topology, VPN, or ExpressRoute — those remain future,
separately-scoped infrastructure PBIs.

## Decision

### Networking introduced

- A production-ready VNet (`ops/bicep/modules/virtual-network.bicep`) with two subnets:
  - `snet-container-apps` (default `/23`, delegated to `Microsoft.App/environments` — required
    for a Consumption-plan Container Apps Environment's VNet integration) — headroom well above
    the `/27` Azure minimum, for future scale.
  - `snet-private-endpoints` (default `/24`, `privateEndpointNetworkPolicies: Disabled`).
- Each subnet has its own NSG with documented, conservative starter rules. These are additive
  ALLOW rules on top of Azure's own non-removable default rules (`AllowVnetInBound`,
  `AllowAzureLoadBalancerInBound`, `DenyAllInBound` at priority 65000+) — see
  `virtual-network.bicep`'s own header comment for why this is an honest starting point, not a
  claim of a fully locked-down deny-by-default posture. Real lockdown (explicit deny overrides)
  needs live testing this PBI did not have the opportunity to perform and is flagged as a good
  candidate for its own future, narrowly-scoped security PBI.
- Four Private Endpoints (`ops/bicep/modules/private-endpoint.bicep`, one reusable module
  instantiated per service) for Azure OpenAI, Azure AI Search, Cosmos DB, and Key Vault, each
  registered in its own Private DNS Zone (`ops/bicep/modules/private-dns-zone.bicep`):
  `privatelink.openai.azure.com`, `privatelink.search.windows.net`,
  `privatelink.documents.azure.com`, `privatelink.vaultcore.azure.net` — Azure's own fixed,
  global DNS suffixes for these services, not customer-specific data.
- A single toggle, `enablePrivateNetworking` (`main.bicep`), controls all of the above plus each
  of the four services' `publicNetworkAccess` (`Disabled` when true). When false, behavior is
  byte-identical to what PBI-03-02 shipped — zero change to the existing default path.
- Key Vault additionally gets `networkAcls: { bypass: 'AzureServices', defaultAction: ... }` so
  this same Bicep template can still write the `appinsights-connection-string` secret
  (`modules/key-vault-secret.bicep`) through the ARM control plane even when the vault's
  data-plane public endpoint is disabled — the standard, documented Azure pattern for deploying
  secrets into a network-restricted vault via IaC.

### Per-environment defaults

- **dev**: `enablePrivateNetworking = false` — matches the same conservative-cost posture already
  applied to Free-tier AI Search and Serverless Cosmos; a disposable dev sandbox does not need
  VNet/Private Endpoint cost or planning.
- **staging/prod**: `enablePrivateNetworking = true`, each with its own non-overlapping VNet CIDR
  (`10.1.0.0/16` / `10.2.0.0/16`) so the two could be peered later without renumbering.

### RBAC audit (no changes required)

Every Azure resource in this template was reviewed against the PBI's required least-privilege
roles. All five were already correct, pre-dating this PBI:

| Resource | Role | Role ID | Scope |
|---|---|---|---|
| Azure OpenAI | Cognitive Services OpenAI User | `5e0bd9bd-7b93-4f28-af87-19fc36ad61bd` | Data-plane, account |
| Azure AI Search | Search Index Data Reader | `1407120a-92aa-4202-b7e9-c0e197c71c8f` | Data-plane, service |
| Cosmos DB | Cosmos DB Built-in Data Contributor | `00000000-0000-0000-0000-000000000002` | Data-plane, account (Cosmos SQL role, not general Azure RBAC) |
| Key Vault | Key Vault Secrets User | `4633458b-17de-408a-b874-0445c86b69e6` | Data-plane, vault |
| ACR | AcrPull | `7f951dda-4ed3-4680-a7ca-43fe172d538d` | Data-plane, registry |

No `Contributor` or `Owner` role is assigned anywhere in `ops/bicep/` (grep-confirmed across
every module). No change was needed — this section exists to record that the audit happened and
passed, per the PBI's own explicit "review every Azure resource" instruction.

### Container Apps ingress

`containerAppsEnvironmentInternal` (default `false` in every environment, including staging/
prod) controls whether the environment gets a public IP. It stays `false` today because Azure
Front Door/Application Gateway are explicitly out of scope for PBI-03-04 — setting it `true`
without one in front would make the platform completely unreachable. **Production
recommendation**: once a future PBI adds Front Door or Application Gateway in front of the Web
(and optionally API) Container App, flip `containerAppsEnvironmentInternal` to `true` and expose
only the Front Door/Gateway publicly — this is the target state the "Internet → Azure Front Door
(optional if already planned) → Container Apps Environment" diagram in that PBI's own
instructions describes.

## What remains deferred (future, separately-scoped infrastructure PBIs)

Explicitly out of scope for PBI-03-04, per its own instructions:

1. **Azure Front Door / Application Gateway / WAF** — required before `containerAppsEnvironmentInternal` can safely become `true`.
2. **Azure Firewall** — for centralized egress control/filtering, if a future posture requires it.
3. **DDoS Protection Plan** — a paid, subscription-level resource; not justified for this academic/reference platform.
4. **Hub-spoke topology** — this ADR's VNet is a single, standalone spoke-shaped network; formal hub-spoke (shared hub VNet, peering, centralized firewall) is a larger organizational decision.
5. **VPN / ExpressRoute** — no on-premises connectivity requirement exists for this platform.
6. **Private Endpoint for ACR** — the target architecture diagram in PBI-03-04's own instructions lists exactly four services (Azure OpenAI, AI Search, Cosmos DB, Key Vault); ACR was not among them, so it remains on its existing public-with-RBAC posture (`AcrPull`-gated, `adminUserEnabled: false`).
7. **Real NSG deny-by-default enforcement** — see the Networking section above.

## Consequences

- `enablePrivateNetworking=true` genuinely removes each of the four services' public network
  surface — not merely RBAC-gated but network-unreachable from outside the VNet — closing the
  gap ADR-0001 named.
- The platform remains fully reachable (external ingress) until Front Door/Application Gateway
  exists; this is a deliberate, documented interim state, not an oversight.
- dev remains cheap and simple to iterate on; staging/prod validate the hardened posture that
  matters for anything beyond synthetic-data academic use.
- Azure AI Search's Free tier does not support Private Link — `enablePrivateNetworking=true`
  requires `aiSearchSkuName` to be `basic` or `standard` (already true for staging/prod; dev
  keeps both `free` and `enablePrivateNetworking=false` together, so no conflict exists today).

## Review triggers

- Before any real deployment against a subscription handling non-synthetic data (per ADR-0001,
  still the overriding condition).
- When a future PBI adds Front Door/Application Gateway — revisit
  `containerAppsEnvironmentInternal`'s default at that point.
- If Azure AI Search's SKU is ever changed to `free` in an environment with
  `enablePrivateNetworking=true` — this combination will fail at deployment time.
- If a real security review recommends explicit NSG deny-by-default rules — the current rules
  are an honest starting point, not a final posture (see Networking section above).

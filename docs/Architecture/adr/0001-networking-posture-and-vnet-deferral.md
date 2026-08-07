# ADR-0001: Networking Posture — Public Network Access + RBAC Today, VNet/Private Endpoints Deferred

## Status

Accepted — 2026-08-07 (PBI-03-02)

## Context

PBI-03-02 completed the Azure runtime wiring: Azure OpenAI, Azure AI Search, Cosmos DB, Key
Vault, and the Container Apps environment are now provisioned and connected end to end via
Managed Identity + RBAC (see `docs/sprint_03/decisions.md` and `docs/sprint_03/validation.md`
for the full inventory). Before closing this PBI, CLAUDE.md §4.5 ("security and privacy by
design") and the PBI's own explicit instruction ("inspect current networking posture and
document what exists versus what is still required for production hardening... do not silently
introduce a large networking redesign") require an honest accounting of what this template does
and does not do at the network layer.

## Current posture (as of PBI-03-02)

Every data-plane resource this template provisions has `publicNetworkAccess: 'Enabled'` (or the
equivalent default) and is reachable from the public internet, gated by:

- **Identity/RBAC only** — Managed Identity + least-privilege built-in role assignments
  (Cognitive Services OpenAI User, Search Index Data Reader, Cosmos DB Data Contributor, Key
  Vault Secrets User, AcrPull), never network-layer restriction.
- **Cosmos DB**: `disableLocalAuth: true` — key-based/connection-string auth is impossible
  regardless of network path; Entra ID identity is mandatory.
- **Azure AI Search / Azure OpenAI**: local (key) auth remains enabled at the resource level
  (deliberate — see PBI-02-02's and PBI-03-02's own decisions.md entries), but the platform's own
  `AzureAISearchProvider`/`AzureOpenAIProvider` default to Managed Identity and only use a key if
  explicitly configured via `SecretProvider`.
- **Key Vault**: RBAC authorization only (`enableRbacAuthorization: true`), no access policies.
- **Container Apps Environment**: not VNet-integrated — it uses the platform-managed, publicly
  routable default environment.
- **No** Private Endpoints, **no** VNet, **no** Network Security Groups, **no** Azure Firewall,
  **no** Front Door/WAF anywhere in this template.

This is a deliberate, conservative-cost posture appropriate for an academic reference platform
handling only synthetic data (CLAUDE.md's own stated data classification for this entire
repository) — not a claim that it meets production network-isolation requirements.

## Decision

Keep the current all-public-network-access + RBAC-only posture for PBI-03-02. Do **not**
introduce VNet integration, Private Endpoints, NSGs, or any other network-layer control as part
of this PBI. This is an explicit scope boundary, not an oversight: PBI-03-02's own instructions
say "do not silently introduce a large networking redesign in this PBI" and "if VNet/private
endpoints are not yet implemented, document them as the next PBI instead of mixing them into this
runtime integration."

## What production hardening would require (deferred, next PBI)

A real production deployment of this reference architecture should, at minimum:

1. **VNet-integrate the Container Apps Environment** (`Microsoft.App/managedEnvironments` with a
   `vnetConfiguration` block), placing the API/Web Container Apps in a private subnet.
2. **Private Endpoints** for Cosmos DB, Azure AI Search, Azure OpenAI, and Key Vault, each with
   `publicNetworkAccess: 'Disabled'` once the corresponding Private Endpoint and Private DNS
   Zone are in place — this removes the internet-reachable surface entirely rather than relying
   on RBAC as the only gate.
3. **Private Endpoint for ACR** (or at least IP-restricted access) so image pulls do not traverse
   the public internet.
4. A **WAF/Front Door or Application Gateway** in front of the Web (and optionally API) Container
   App if it must remain externally reachable, rather than exposing the Container App's default
   public ingress directly.
5. **Network Security Groups** on the VNet subnets, and a review of whether Container Apps'
   platform-managed outbound path is acceptable or needs a NAT Gateway for a stable egress IP
   (relevant if any downstream Azure service needs IP allow-listing).
6. Re-evaluation of `disableLocalAuth` for Azure AI Search/Azure OpenAI once/if the opt-in
   key-auth requirement that currently keeps it enabled is retired.

## Consequences

- This template remains deployable without requiring VNet/subnet/DNS zone planning up front,
  keeping it appropriate for its stated academic/reference purpose.
- Anyone adapting this repository for a real production workload with real (non-synthetic) data
  must treat the items above as required, not optional, before doing so — CLAUDE.md's own
  disclaimer ("this repository does not represent an officially approved TMX production
  architecture") already establishes this, and this ADR makes the specific network-layer gap
  explicit rather than implicit.
- The next PBI that addresses networking should reference this ADR rather than re-deriving the
  gap analysis, and should itself be scoped narrowly (e.g., "VNet-integrate the Container Apps
  Environment" as one PBI, "Private Endpoints for data-plane services" as another) rather than
  attempted as a single large redesign.

## Review triggers

- Before any deployment of this template against a subscription handling non-synthetic data.
- If a future PBI enables `azure_openai_use_api_key`/`azure_ai_search_use_api_key` in a
  long-lived environment (raises the value of closing the public-network-access gap sooner).
- If Azure Policy or organizational governance in a target subscription mandates Private
  Endpoints or denies public network access on these resource types.

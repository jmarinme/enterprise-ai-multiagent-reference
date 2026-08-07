# Networking Topology (PBI-03-04)

Source of truth: `ops/bicep/main.bicep` + `ops/bicep/modules/{virtual-network,private-endpoint,
private-dns-zone,container-apps-environment,cosmos-db,ai-search,azure-openai,key-vault}.bicep`.
See `docs/Architecture/adr/0001-networking-posture-and-vnet-deferral.md` and
`docs/Architecture/adr/0002-vnet-private-endpoints-hardening.md` for the decisions behind this
diagram, including what is deliberately still out of scope (Front Door, WAF, Azure Firewall,
DDoS Plan, hub-spoke, VPN, ExpressRoute).

This is the topology when `enablePrivateNetworking = true` (staging/prod default). When
`false` (dev default), the VNet/subnets/NSGs/Private Endpoints/Private DNS Zones below simply
do not exist, and every service keeps the public, RBAC-gated posture ADR-0001 described.

```mermaid
flowchart TB
    Internet(["Internet"])

    subgraph FD["Azure Front Door — future PBI, NOT built here"]
        FDNote["Optional WAF/Front Door in front of\nexternal ingress once implemented"]
    end

    subgraph CAE["Container Apps Environment (externally reachable today —\ncontainerAppsEnvironmentInternal=false, see ADR-0002)"]
        API["API Container App\n(Managed Identity)"]
        WEB["Web Container App"]
    end

    subgraph VNET["VNet (10.x.0.0/16, per-environment CIDR)"]
        subgraph SNET_CA["snet-container-apps (/23)\ndelegated: Microsoft.App/environments\nNSG: nsg-*-container-apps"]
            API
            WEB
        end

        subgraph SNET_PE["snet-private-endpoints (/24)\nprivateEndpointNetworkPolicies: Disabled\nNSG: nsg-*-private-endpoints"]
            PE_AOAI["Private Endpoint\nAzure OpenAI (account)"]
            PE_SEARCH["Private Endpoint\nAI Search (searchService)"]
            PE_COSMOS["Private Endpoint\nCosmos DB (Sql)"]
            PE_KV["Private Endpoint\nKey Vault (vault)"]
        end
    end

    subgraph DNS["Private DNS Zones (linked to VNet)"]
        DNS_AOAI["privatelink.openai.azure.com"]
        DNS_SEARCH["privatelink.search.windows.net"]
        DNS_COSMOS["privatelink.documents.azure.com"]
        DNS_KV["privatelink.vaultcore.azure.net"]
    end

    subgraph SVC["Azure Services — publicNetworkAccess: Disabled"]
        AOAI["Azure OpenAI\n(RBAC: Cognitive Services OpenAI User)"]
        SEARCH["Azure AI Search\n(RBAC: Search Index Data Reader)"]
        COSMOS["Cosmos DB\n(RBAC: Data Contributor, disableLocalAuth: true)"]
        KV["Key Vault\n(RBAC: Key Vault Secrets User, networkAcls.bypass: AzureServices)"]
    end

    ACR["Azure Container Registry\n(RBAC: AcrPull — public, unchanged, see ADR-0002 §6)"]

    Internet -.->|"future: WAF/Front Door"| FD
    Internet -->|"HTTPS 443 (today)"| API
    Internet --> WEB

    API -->|"Managed Identity token"| PE_AOAI --> DNS_AOAI --> AOAI
    API -->|"Managed Identity token"| PE_SEARCH --> DNS_SEARCH --> SEARCH
    API -->|"Managed Identity token"| PE_COSMOS --> DNS_COSMOS --> COSMOS
    API -->|"Managed Identity token"| PE_KV --> DNS_KV --> KV
    API -.->|"image pull, AcrPull\n(public, no Private Endpoint)"| ACR

    classDef future stroke-dasharray: 5 5,opacity:0.6;
    class FD,FDNote future
```

## Reading this diagram

- **Solid arrows** exist today when `enablePrivateNetworking = true`. **Dashed** elements
  (Azure Front Door) are explicitly deferred — see ADR-0002.
- The API Container App reaches all four data-plane services exclusively through their Private
  Endpoints once `enablePrivateNetworking = true` — `AzureOpenAIProvider`,
  `AzureAISearchProvider`, and `CosmosConversationRepository` require **zero code change**: the
  Private DNS Zones resolve each service's existing public hostname to its private IP
  transparently.
- ACR remains on its pre-existing public endpoint (RBAC-gated via `AcrPull`) — not one of the
  four services this PBI's target architecture named for Private Link.
- Ingress stays external (`containerAppsEnvironmentInternal = false`) in every environment
  until a future PBI adds Front Door/Application Gateway — flipping it today would make the
  platform unreachable.

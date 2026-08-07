// Production-ready VNet for the Azure runtime (PBI-03-04), fulfilling ADR-0001's own named
// follow-up. Two subnets, each with its own NSG:
//   - containerApps: hosts the Container Apps Environment's VNet integration (delegated to
//     Microsoft.App/environments, required for a Consumption-plan environment). Sized /23 by
//     default — comfortably above the /27 minimum Azure requires, leaving headroom for future
//     scale (more replicas, workload profiles) without a resize.
//   - privateEndpoints: hosts the four Private Endpoints (Azure OpenAI, Azure AI Search,
//     Cosmos DB, Key Vault) wired in main.bicep. privateEndpointNetworkPolicies is disabled,
//     the standard, broadly-compatible setting for a subnet dedicated to Private Endpoints.
//
// NSG rules here are deliberately conservative starter rules, not a complete lockdown: Azure
// always keeps its own default rules (AllowVnetInBound, AllowAzureLoadBalancerInBound,
// DenyAllInBound at priority 65000+) beneath whatever custom rules a template adds — ARM
// provides no way to remove them. That means the explicit "allow 443 from containerApps
// subnet only" rule on the privateEndpoints NSG is, today, already implied by the default
// AllowVnetInBound rule; it exists here to make the *intended* traffic pattern explicit and
// reviewable, and to be the natural place a future, dedicated security-hardening PBI adds a
// real deny-by-default override once it can be properly tested. See
// docs/Architecture/adr/0002-vnet-private-endpoints-hardening.md.
//
// No subscription, tenant, resource group, or IP range is hardcoded here — every address
// prefix is a parameter with a documented default, overridable per environment.

@description('Azure region for all networking resources.')
param location string

@description('Resource tags applied for project, environment, purpose, data classification, and ownership traceability.')
param tags object

@description('VNet resource name.')
param name string

@description('VNet address space (CIDR). Never hardcoded — override per environment if it must not collide with an existing network.')
param addressPrefix string = '10.0.0.0/16'

@description('Container Apps Environment subnet address prefix. Must be at least /27; /23 default leaves headroom for future scale.')
param containerAppsSubnetPrefix string = '10.0.0.0/23'

@description('Private Endpoints subnet address prefix.')
param privateEndpointsSubnetPrefix string = '10.0.2.0/24'

var containerAppsSubnetName = 'snet-container-apps'
var privateEndpointsSubnetName = 'snet-private-endpoints'

resource containerAppsNsg 'Microsoft.Network/networkSecurityGroups@2023-11-01' = {
  name: 'nsg-${name}-container-apps'
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'AllowAzureLoadBalancerInbound'
        properties: {
          description: 'Required for the Container Apps platform health probes.'
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: 'AzureLoadBalancer'
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'AllowHttpsInbound'
        properties: {
          description: 'External ingress (HTTPS only) for the API/Web Container Apps. Revisit once containerAppsEnvironmentInternal=true is paired with a Front Door/Application Gateway in front (out of scope for PBI-03-04 — see the ADR).'
          priority: 110
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '443'
          sourceAddressPrefix: 'Internet'
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
}

resource privateEndpointsNsg 'Microsoft.Network/networkSecurityGroups@2023-11-01' = {
  name: 'nsg-${name}-private-endpoints'
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'AllowHttpsFromContainerAppsSubnet'
        properties: {
          description: 'Only the Container Apps subnet needs to reach the Private Endpoints (Azure OpenAI, AI Search, Cosmos DB, Key Vault all speak HTTPS/443). See this module\'s own header comment for why this is currently additive to, not a replacement for, Azure\'s default AllowVnetInBound rule.'
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '443'
          sourceAddressPrefix: containerAppsSubnetPrefix
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2023-11-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        addressPrefix
      ]
    }
    subnets: [
      {
        name: containerAppsSubnetName
        properties: {
          addressPrefix: containerAppsSubnetPrefix
          networkSecurityGroup: {
            id: containerAppsNsg.id
          }
          delegations: [
            {
              name: 'Microsoft.App.environments'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }
      }
      {
        name: privateEndpointsSubnetName
        properties: {
          addressPrefix: privateEndpointsSubnetPrefix
          networkSecurityGroup: {
            id: privateEndpointsNsg.id
          }
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
    ]
  }
}

output id string = vnet.id
output name string = vnet.name
output containerAppsSubnetId string = '${vnet.id}/subnets/${containerAppsSubnetName}'
output privateEndpointsSubnetId string = '${vnet.id}/subnets/${privateEndpointsSubnetName}'

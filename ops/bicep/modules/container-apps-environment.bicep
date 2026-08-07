// Azure Container Apps (Consumption) managed environment. This materializes ADR-001
// (Container Apps chosen over AKS for this platform's scale/complexity) as code.
//
// VNet integration (PBI-03-04, optional/opt-in via infrastructureSubnetId): when a subnet ID
// is supplied, the environment's API/Web Container Apps run inside that subnet — see
// modules/virtual-network.bicep for the subnet itself (delegated to Microsoft.App/environments,
// as a Consumption-plan environment requires). When infrastructureSubnetId is empty (the
// default, and dev's own default via enablePrivateNetworking=false), this resource is
// identical to the pre-PBI-03-04 public Consumption environment — zero behavior change.
//
// internal controls whether the environment gets a public IP (false, the default — required
// for the platform to remain reachable at all, since Azure Front Door/Application Gateway are
// explicitly out of scope for PBI-03-04) or is fully private, reachable only from inside the
// VNet (true — the eventual production target once a Front Door/Application Gateway exists in
// front of it; see docs/Architecture/adr/0002-vnet-private-endpoints-hardening.md).

@description('Azure region for the Container Apps environment.')
param location string

@description('Container Apps environment resource name.')
param name string

@description('Resource tags applied for project, environment, purpose, data classification, and ownership traceability.')
param tags object

@description('Log Analytics workspace customer (workspace) ID used as the log destination.')
param logAnalyticsCustomerId string

@secure()
@description('Log Analytics workspace shared key used as the log destination credential.')
param logAnalyticsSharedKey string

@description('Resource ID of the subnet to VNet-integrate this environment into (modules/virtual-network.bicep\'s containerAppsSubnetId output). Empty string (the default) leaves the environment as the pre-PBI-03-04 public, non-VNet-integrated Consumption environment.')
param infrastructureSubnetId string = ''

@description('Whether the environment is fully internal (no public IP). Only meaningful when infrastructureSubnetId is set. Defaults to false: without a Front Door/Application Gateway in front (out of scope for PBI-03-04), true would make the platform unreachable.')
param internal bool = false

var hasVnetIntegration = !empty(infrastructureSubnetId)

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsCustomerId
        sharedKey: logAnalyticsSharedKey
      }
    }
    zoneRedundant: false
    vnetConfiguration: hasVnetIntegration ? {
      infrastructureSubnetId: infrastructureSubnetId
      internal: internal
    } : null
  }
}

output id string = environment.id
output name string = environment.name
output defaultDomain string = environment.properties.defaultDomain

// Azure Container Apps (Consumption) managed environment. This materializes ADR-001
// (Container Apps chosen over AKS for this platform's scale/complexity) as code.
// No VNet integration in Sprint 0 — public Consumption environment only.

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
  }
}

output id string = environment.id
output name string = environment.name
output defaultDomain string = environment.properties.defaultDomain

// Claims Tool Layer + Durable Functions Function App (PBI-06-01) — resolves Architecture
// Review Finding A-03. Linux, Python 3.12, App Service Plan SKU parameterized (Y1 architectural
// default; B1/P0v4 are quota-driven fallbacks — see appServicePlanSkuName below and
// docs/Architecture/adr/0003-azure-functions-tool-and-workflow-layer.md). Uses the platform's existing
// shared user-assigned Managed Identity (CLAUDE.md §4.5) for Storage (AzureWebJobsStorage,
// identity-based, no account key) and for its Key Vault-backed App Insights connection string
// — the same identity ops/bicep/modules/container-app.bicep already uses for the API/Web
// Container Apps, reused here rather than provisioning a second identity for one more compute
// resource on the same platform.

@description('Azure region for the Function App and its App Service Plan.')
param location string

@description('Function App resource name. Must be globally unique (azurewebsites.net).')
param name string

@description('App Service Plan resource name.')
param appServicePlanName string

@description('Resource tags applied for project, environment, purpose, data classification, and ownership traceability.')
param tags object

@description('Name of the storage account backing AzureWebJobsStorage and the Durable Task Hub (identity-based access, no key).')
param storageAccountName string

@description('Resource ID of the user-assigned managed identity used for Storage and Key Vault secret access.')
param userAssignedIdentityId string

@description('Client ID of the user-assigned managed identity — required by AzureWebJobsStorage__clientId and by DefaultAzureCredential to disambiguate which identity to use (same requirement as the API Container App; see ops/bicep/main.bicep AZURE_CLIENT_ID comment).')
param userAssignedIdentityClientId string

@description('Key Vault secret URI (versionless) for the Application Insights connection string, referenced via a Key Vault reference app setting rather than a plain-text value.')
param appInsightsConnectionStringSecretUri string

@description('Plain (non-secret) application settings as { name, value } objects — same shape as ops/bicep/modules/container-app.bicep\'s env param, for consistency.')
param appSettings array = []

@description('App Service Plan SKU. Y1 (Consumption, pay-per-execution) is the architectural default for a serverless Tool Layer. B1 (Basic, small fixed monthly cost, always-on) is a documented fallback for subscriptions with 0 quota on the Dynamic/Consumption VM family. P0v4 (Premium v4, Dedicated) is a DEV-only workaround for subscriptions with 0 quota on both the Dynamic and Basic/Standard/PremiumV2/V3 VM families but nonzero Premium v4 quota — not a production hosting recommendation. See docs/Architecture/adr/0003-azure-functions-tool-and-workflow-layer.md.')
@allowed(['Y1', 'B1', 'P0v4'])
param appServicePlanSkuName string = 'Y1'

var appServicePlanTier = appServicePlanSkuName == 'Y1' ? 'Dynamic' : (appServicePlanSkuName == 'B1' ? 'Basic' : 'PremiumV4')

// Consumption (Y1) has no Always On setting (serverless, cold-start-by-design). Dedicated plans
// (B1, P0v4) need Always On so the Function App/Durable Task Hub host is not idled out between
// requests — required for the Durable Functions orchestrator to make forward progress reliably.
var functionAppAlwaysOn = appServicePlanSkuName != 'Y1'

resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: appServicePlanName
  location: location
  tags: tags
  sku: {
    name: appServicePlanSkuName
    tier: appServicePlanTier
  }
  kind: 'functionapp'
  properties: {
    reserved: true
  }
}

resource functionApp 'Microsoft.Web/sites@2023-01-01' = {
  name: name
  location: location
  tags: tags
  kind: 'functionapp,linux'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${userAssignedIdentityId}': {}
    }
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    keyVaultReferenceIdentity: userAssignedIdentityId
    siteConfig: {
      linuxFxVersion: 'Python|3.12'
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      alwaysOn: functionAppAlwaysOn
      appSettings: concat(
        [
          { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
          { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
          { name: 'AzureWebJobsFeatureFlags', value: 'EnableWorkerIndexing' }
          { name: 'WEBSITE_RUN_FROM_PACKAGE', value: '1' }
          // Identity-based AzureWebJobsStorage (no storage account key exists to leak — see
          // ops/bicep/modules/storage-account.bicep, allowSharedKeyAccess: false).
          { name: 'AzureWebJobsStorage__accountName', value: storageAccountName }
          { name: 'AzureWebJobsStorage__credential', value: 'managedidentity' }
          { name: 'AzureWebJobsStorage__clientId', value: userAssignedIdentityClientId }
          { name: 'AZURE_CLIENT_ID', value: userAssignedIdentityClientId }
          {
            name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
            value: '@Microsoft.KeyVault(SecretUri=${appInsightsConnectionStringSecretUri})'
          }
        ],
        appSettings
      )
    }
  }
}

output id string = functionApp.id
output name string = functionApp.name
output defaultHostName string = functionApp.properties.defaultHostName

// Application Insights (workspace-based) — request/dependency telemetry correlated via
// the platform's correlationId (see CLAUDE.md §10 observability requirements).

@description('Azure region for the Application Insights resource.')
param location string

@description('Application Insights resource name.')
param name string

@description('Resource tags applied for project, environment, purpose, data classification, and ownership traceability.')
param tags object

@description('Resource ID of the Log Analytics workspace backing this workspace-based Application Insights resource.')
param logAnalyticsWorkspaceId string

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: name
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsWorkspaceId
    IngestionMode: 'LogAnalytics'
  }
}

output id string = appInsights.id
output name string = appInsights.name

@description('Connection string used only to seed a Key Vault secret; never output as plain deployment output elsewhere.')
output connectionString string = appInsights.properties.ConnectionString

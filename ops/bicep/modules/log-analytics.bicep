// Log Analytics Workspace — sink for Container Apps environment logs and Application Insights.
// Workspace-based telemetry is the current Microsoft-recommended pattern (vs. classic App Insights).

@description('Azure region for the workspace.')
param location string

@description('Workspace resource name.')
param name string

@description('Resource tags applied for project, environment, purpose, data classification, and ownership traceability.')
param tags object

@description('Log retention in days.')
@minValue(30)
@maxValue(730)
param retentionInDays int = 30

@description('Optional daily ingestion cap in GB to bound cost. Use -1 for no cap.')
param dailyQuotaGb int = -1

resource workspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: retentionInDays
    workspaceCapping: {
      dailyQuotaGb: dailyQuotaGb
    }
  }
}

output id string = workspace.id
output name string = workspace.name

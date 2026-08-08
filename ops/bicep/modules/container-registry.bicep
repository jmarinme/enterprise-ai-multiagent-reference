// Azure Container Registry. Admin user is disabled: image pulls are authenticated via the
// platform's user-assigned Managed Identity + AcrPull role assignment, never shared credentials.

@description('Azure region for the registry.')
param location string

@description('Registry resource name. Must be globally unique, 5-50 alphanumeric characters (no hyphens).')
param name string

@description('Resource tags applied for project, environment, purpose, data classification, and ownership traceability.')
param tags object

@description('Registry SKU.')
@allowed(['Basic', 'Standard', 'Premium'])
param skuName string = 'Basic'

@description('Principal ID of the identity granted the built-in "AcrPull" role on this registry. Empty string skips the role assignment.')
param pullPrincipalId string = ''

@description('Principal ID of the identity granted the built-in "AcrPush" role on this registry — needed by the CI/CD pipeline to push newly built images (PBI-04-01). Empty string skips the role assignment. Reuses the same platform Managed Identity that already holds AcrPull, via Workload Identity Federation with the Azure DevOps service connection — no new identity, no stored credential.')
param pushPrincipalId string = ''

var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var acrPushRoleId = '8311e382-0749-4cb8-b61a-304f252e45ec'

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: skuName
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

resource acrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(pullPrincipalId)) {
  name: guid(registry.id, pullPrincipalId, acrPullRoleId)
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
    principalId: pullPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource acrPushRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(pushPrincipalId)) {
  name: guid(registry.id, pushPrincipalId, acrPushRoleId)
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPushRoleId)
    principalId: pushPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output id string = registry.id
output name string = registry.name
output loginServer string = registry.properties.loginServer

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

var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

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

output id string = registry.id
output name string = registry.name
output loginServer string = registry.properties.loginServer

// Key Vault foundation. Sprint 0 scope: no business secrets yet (Cosmos DB, Azure OpenAI, and
// other data-plane secrets are explicitly out of scope for this PBI). RBAC authorization is used
// (not vault access policies) to keep authorization consistent with the platform's Managed
// Identity + RBAC model (CLAUDE.md §4.5).

@description('Azure region for the Key Vault.')
param location string

@description('Key Vault resource name. Must be globally unique, 3-24 alphanumeric/hyphen characters.')
param name string

@description('Resource tags applied for project, environment, purpose, data classification, and ownership traceability.')
param tags object

@description('Key Vault SKU.')
@allowed(['standard', 'premium'])
param skuName string = 'standard'

@description('Enable purge protection. Once enabled it cannot be disabled; keep false for disposable dev sandboxes, true for staging/prod.')
param enablePurgeProtection bool = false

@description('Principal ID of the identity granted the built-in "Key Vault Secrets User" role on this vault. Empty string skips the role assignment.')
param keyVaultAccessPrincipalId string = ''

var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: skuName
    }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: enablePurgeProtection ? true : null
    publicNetworkAccess: 'Enabled'
  }
}

resource secretsUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(keyVaultAccessPrincipalId)) {
  name: guid(keyVault.id, keyVaultAccessPrincipalId, keyVaultSecretsUserRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalId: keyVaultAccessPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output id string = keyVault.id
output name string = keyVault.name
output uri string = keyVault.properties.vaultUri
output tenantId string = keyVault.properties.tenantId

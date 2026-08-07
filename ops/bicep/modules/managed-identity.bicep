// User-assigned Managed Identity shared by the API and Web Container Apps for:
//  - Pulling images from Azure Container Registry (no registry credentials stored anywhere).
//  - Reading secrets from Key Vault via Container Apps Key Vault references.
// CLAUDE.md §4.5: service-to-service authentication must use Managed Identity.

@description('Azure region for the managed identity.')
param location string

@description('Managed identity resource name.')
param name string

@description('Resource tags applied for project, environment, purpose, data classification, and ownership traceability.')
param tags object

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: name
  location: location
  tags: tags
}

output id string = identity.id
output name string = identity.name
output principalId string = identity.properties.principalId
output clientId string = identity.properties.clientId

// Generic, reusable Private DNS Zone + VNet link (PBI-03-04). Instantiated once per Azure
// service that gets a Private Endpoint (Azure OpenAI, Azure AI Search, Cosmos DB, Key Vault —
// see main.bicep), mirroring how modules/container-app.bicep is already instantiated twice
// for API and Web rather than writing the resource block out repeatedly.
//
// zoneName is the well-known, fixed "privatelink.*" DNS suffix Azure itself defines for each
// service (e.g. "privatelink.openai.azure.com") — a global platform constant, not
// environment-specific data, so it is passed in by the caller (main.bicep) rather than
// guessed or hardcoded inside this generic module. This is the same category of constant as
// the built-in RBAC role GUIDs already hardcoded as `var`s throughout every other module in
// this folder (e.g. ops/bicep/modules/key-vault.bicep's keyVaultSecretsUserRoleId) — never a
// subscription, tenant, resource group, or customer-specific value.

@description('Private DNS zone name — a fixed Azure "privatelink.*" suffix supplied by the caller, never guessed here.')
param zoneName string

@description('Resource ID of the VNet to link this zone to.')
param vnetId string

@description('Resource tags applied for project, environment, purpose, data classification, and ownership traceability.')
param tags object

resource zone 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: zoneName
  location: 'global'
  tags: tags
}

resource vnetLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: zone
  name: 'link-${uniqueString(vnetId)}'
  location: 'global'
  tags: tags
  properties: {
    virtualNetwork: {
      id: vnetId
    }
    registrationEnabled: false
  }
}

output id string = zone.id
output name string = zone.name

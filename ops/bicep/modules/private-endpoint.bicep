// Generic, reusable Private Endpoint + Private DNS Zone Group (PBI-03-04). Instantiated once
// per Azure service that needs one (Azure OpenAI, Azure AI Search, Cosmos DB, Key Vault — see
// main.bicep), the same reuse pattern already established by modules/private-dns-zone.bicep
// and modules/container-app.bicep.
//
// The DNS Zone Group is what makes this "just work" for the platform's own DefaultAzureCredential
// clients (AzureOpenAIProvider, AzureAISearchProvider, CosmosConversationRepository): once
// wired, the target resource's public hostname resolves, from inside the VNet, to the Private
// Endpoint's private IP automatically — no code change, no endpoint URL change, required in
// any of those providers.

@description('Azure region for the Private Endpoint.')
param location string

@description('Private Endpoint resource name.')
param name string

@description('Resource tags applied for project, environment, purpose, data classification, and ownership traceability.')
param tags object

@description('Resource ID of the subnet the Private Endpoint\'s NIC is created in.')
param subnetId string

@description('Resource ID of the target Azure resource (Cognitive Services account, Search service, Cosmos DB account, or Key Vault) this Private Endpoint connects to.')
param targetResourceId string

@description('Private Link sub-resource (group ID) to connect to — e.g. "account" (Azure OpenAI), "searchService" (Azure AI Search), "Sql" (Cosmos DB SQL API), "vault" (Key Vault).')
param groupId string

@description('Resource ID of the Private DNS zone to register this endpoint\'s A record in.')
param privateDnsZoneId string

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2023-11-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    subnet: {
      id: subnetId
    }
    privateLinkServiceConnections: [
      {
        name: name
        properties: {
          privateLinkServiceId: targetResourceId
          groupIds: [
            groupId
          ]
        }
      }
    ]
  }
}

resource dnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = {
  parent: privateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: groupId
        properties: {
          privateDnsZoneId: privateDnsZoneId
        }
      }
    ]
  }
}

output id string = privateEndpoint.id
output name string = privateEndpoint.name

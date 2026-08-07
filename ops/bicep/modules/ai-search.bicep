// Azure AI Search — production-shaped backing store for the AzureAISearchProvider
// KnowledgeProvider (PBI-02-02). Free tier is the conservative default: $0 cost, sufficient
// for a synthetic reference-document corpus, and this PBI explicitly excludes semantic
// ranking and ingestion pipelines, neither of which the Free tier supports anyway — so its
// limits are not a real constraint here.
//
// RBAC-only data-plane access: the shared Managed Identity is granted the built-in
// "Search Index Data Reader" role, matching CLAUDE.md §4.5's Managed Identity preference. Key
// authentication is left enabled at the service level (disableLocalAuth stays false, unlike
// the Cosmos DB module) because this PBI explicitly requires an opt-in key-auth path via
// SecretProvider to remain possible for AzureAISearchProvider — no key is created, stored, or
// output by this module; a future PBI that enables key auth must place the key in Key Vault
// out of band and reference it by secret name only.
//
// Index creation and document ingestion are explicitly out of scope for this PBI — this module
// only provisions the search SERVICE, not any index or data.

@description('Azure region for the Azure AI Search service.')
param location string

@description('Azure AI Search service name. Must be globally unique, lowercase alphanumeric/hyphen, 2-60 characters.')
param name string

@description('Resource tags applied for project, environment, purpose, data classification, and ownership traceability.')
param tags object

@description('Azure AI Search pricing tier. Free is the conservative default for dev/academic use.')
@allowed(['free', 'basic', 'standard'])
param skuName string = 'free'

@description('Number of replicas. The free tier supports exactly 1; only meaningful for basic/standard.')
@minValue(1)
@maxValue(12)
param replicaCount int = 1

@description('Number of partitions. The free tier supports exactly 1; only meaningful for basic/standard.')
@minValue(1)
@maxValue(12)
param partitionCount int = 1

@description('Principal ID of the identity granted the built-in "Search Index Data Reader" role. Empty string skips the role assignment.')
param searchIndexDataReaderPrincipalId string = ''

@description('Whether the service is reachable over its public endpoint. Set false once a Private Endpoint is provisioned for production hardening (PBI-03-04) — see main.bicep\'s enablePrivateNetworking param. NOTE: Azure AI Search\'s Free tier does not support Private Link at all — this must stay true unless skuName is basic/standard.')
param enablePublicNetworkAccess bool = true

var searchIndexDataReaderRoleId = '1407120a-92aa-4202-b7e9-c0e197c71c8f'
var isFreeTier = skuName == 'free'

resource searchService 'Microsoft.Search/searchServices@2023-11-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: skuName
  }
  properties: {
    replicaCount: isFreeTier ? 1 : replicaCount
    partitionCount: isFreeTier ? 1 : partitionCount
    hostingMode: 'default'
    publicNetworkAccess: enablePublicNetworkAccess ? 'enabled' : 'disabled'
    disableLocalAuth: false
  }
}

resource searchIndexDataReaderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(searchIndexDataReaderPrincipalId)) {
  name: guid(searchService.id, searchIndexDataReaderPrincipalId, searchIndexDataReaderRoleId)
  scope: searchService
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchIndexDataReaderRoleId)
    principalId: searchIndexDataReaderPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output id string = searchService.id
output name string = searchService.name
output endpoint string = 'https://${searchService.name}.search.windows.net'

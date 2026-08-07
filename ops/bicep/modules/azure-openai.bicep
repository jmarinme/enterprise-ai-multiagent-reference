// Azure OpenAI — production-shaped backing service for the AzureOpenAIProvider LLMProvider
// (PBI-01-04, wired to the Azure runtime by PBI-03-02). Provisions the Cognitive Services
// "OpenAI" account and exactly one chat-completion model deployment; no fine-tuning, no
// additional deployments, no content-filter customization — none were requested.
//
// RBAC-only data-plane access: the shared Managed Identity is granted the built-in "Cognitive
// Services OpenAI User" role, matching CLAUDE.md §4.5's Managed Identity preference and this
// platform's existing Cosmos DB/AI Search precedent. Key authentication is left enabled at the
// service level (disableLocalAuth is not set, so it defaults to false) — the SAME deliberate
// choice already made for Azure AI Search (see ops/bicep/modules/ai-search.bicep and
// docs/sprint_02/decisions.md): AzureOpenAIProvider explicitly supports an opt-in
// azure_openai_use_api_key path via SecretProvider, so the resource-level door must stay open
// for that path to remain real and usable. No key is created, stored, or output by this module.
//
// customSubDomainName is required for Entra ID / Managed Identity token-based auth to work at
// all against a Cognitive Services resource — omitting it would silently force key-only auth.
//
// Model/capacity choice, and Azure subscription-level OpenAI quota approval, are deployment-time
// concerns outside what Bicep itself can guarantee — see docs/sprint_03/decisions.md.

@description('Azure region for the Azure OpenAI account. Azure OpenAI is only available in a subset of regions — verify quota/availability before deploying.')
param location string

@description('Azure OpenAI account name. Must be globally unique (becomes part of the custom subdomain DNS name), 2-64 alphanumeric/hyphen characters.')
param name string

@description('Resource tags applied for project, environment, purpose, data classification, and ownership traceability.')
param tags object

@description('Cognitive Services pricing tier. S0 (Standard) is the only tier Azure OpenAI deployments support.')
@allowed(['S0'])
param skuName string = 'S0'

@description('Model deployment name — this is the value AZURE_OPENAI_DEPLOYMENT/LLMSettings.azure_openai_deployment must reference.')
param deploymentName string = 'chat'

@description('Underlying OpenAI model name to deploy.')
param modelName string = 'gpt-4o-mini'

@description('Underlying OpenAI model version to deploy.')
param modelVersion string = '2024-07-18'

@description('Deployment capacity in units of 1,000 tokens-per-minute (TPM). Conservative default sized for dev/academic use — increase per environment via the parameter files.')
@minValue(1)
param modelCapacity int = 10

@description('Principal ID of the identity granted the built-in "Cognitive Services OpenAI User" role. Empty string skips the role assignment.')
param openAiUserPrincipalId string = ''

@description('Whether the account is reachable over its public endpoint. Set false once a Private Endpoint is provisioned for production hardening (PBI-03-04) — see main.bicep\'s enablePrivateNetworking param.')
param enablePublicNetworkAccess bool = true

var cognitiveServicesOpenAiUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

resource account 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: name
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: {
    name: skuName
  }
  properties: {
    customSubDomainName: name
    publicNetworkAccess: enablePublicNetworkAccess ? 'Enabled' : 'Disabled'
  }
}

resource deployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: account
  name: deploymentName
  sku: {
    name: 'Standard'
    capacity: modelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
  }
}

resource openAiUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(openAiUserPrincipalId)) {
  name: guid(account.id, openAiUserPrincipalId, cognitiveServicesOpenAiUserRoleId)
  scope: account
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAiUserRoleId)
    principalId: openAiUserPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output id string = account.id
output name string = account.name
output endpoint string = account.properties.endpoint
output deploymentName string = deployment.name

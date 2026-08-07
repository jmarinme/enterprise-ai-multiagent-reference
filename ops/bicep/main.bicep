// TMX Enterprise AI Reference Platform — Sprint 0 Bicep foundation (PBI-00-04, extended by
// PBI-00-05 with the Cosmos DB conversation store).
//
// Scope: Container Registry, Log Analytics, Application Insights, Container Apps environment,
// API + Web Container Apps, a shared user-assigned Managed Identity, a Key Vault foundation,
// and a Cosmos DB for NoSQL conversation history store.
//
// Explicitly out of scope (later PBIs/ADRs): Azure OpenAI, Azure AI Search, API Management,
// Storage accounts, agent business logic, RAG.
//
// Deploys into an existing resource group supplied at deploy time (`az deployment group create
// --resource-group <rg>`) — the resource group name is intentionally never referenced here.

targetScope = 'resourceGroup'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Deployment environment. Drives conservative-vs-larger scaling and protection defaults via the parameter files, not this template.')
@allowed(['dev', 'staging', 'prod'])
param environmentName string

@description('Short, generic project identifier used to build resource names. Safe for a public academic reference repository.')
param projectName string = 'tmxai'

@description('Tag value describing what this resource group is for.')
param purpose string = 'academic-reference-platform'

@description('Tag value describing the data classification of everything this platform handles in Sprint 0 and beyond.')
param dataClassification string = 'synthetic'

@description('Azure Container Registry SKU.')
@allowed(['Basic', 'Standard', 'Premium'])
param acrSkuName string = 'Basic'

@description('Log Analytics workspace retention in days.')
@minValue(30)
@maxValue(730)
param logAnalyticsRetentionInDays int = 30

@description('Log Analytics daily ingestion cap in GB, for cost control. Use -1 for no cap.')
param logAnalyticsDailyQuotaGb int = -1

@description('Whether Key Vault purge protection is enabled. Once enabled it cannot be disabled — keep false only for disposable dev sandboxes.')
param keyVaultEnablePurgeProtection bool = false

@description('SQL API database name for the conversation history store.')
param cosmosDatabaseName string = '${projectName}-conversation-db'

@description('Conversation container name.')
param cosmosContainerName string = 'conversations'

@description('Cosmos DB consistency level.')
@allowed(['Eventual', 'ConsistentPrefix', 'Session', 'BoundedStaleness', 'Strong'])
param cosmosConsistencyLevel string = 'Session'

@description('Cosmos DB capacity mode. Serverless is the conservative default for dev/academic use.')
@allowed(['Serverless', 'Provisioned'])
param cosmosCapacityMode string = 'Serverless'

@description('Cosmos DB manual throughput (RU/s), used only when cosmosCapacityMode is Provisioned.')
@minValue(400)
param cosmosThroughput int = 400

@description('Conversation container default TTL in seconds. -1 provisions TTL support without expiring anything by default; a real retention value requires its own ADR.')
param cosmosConversationTtlSeconds int = -1

@description('API image repository name inside the registry.')
param apiImageName string

@description('API image tag to deploy. Must be supplied by the environment parameter file — never defaulted here.')
param apiImageTag string

@description('API container CPU cores, e.g. 0.25.')
param apiCpuCores string = '0.25'

@description('API container memory, e.g. 0.5Gi.')
param apiMemory string = '0.5Gi'

@description('API Container App minimum replica count.')
@minValue(0)
param apiMinReplicas int = 1

@description('API Container App maximum replica count.')
@minValue(1)
param apiMaxReplicas int = 1

@description('Web image repository name inside the registry.')
param webImageName string

@description('Web image tag to deploy. Must be supplied by the environment parameter file — never defaulted here.')
param webImageTag string

@description('Web container CPU cores, e.g. 0.25.')
param webCpuCores string = '0.25'

@description('Web container memory, e.g. 0.5Gi.')
param webMemory string = '0.5Gi'

@description('Web Container App minimum replica count.')
@minValue(0)
param webMinReplicas int = 1

@description('Web Container App maximum replica count.')
@minValue(1)
param webMaxReplicas int = 1

var tags = {
  project: projectName
  environment: environmentName
  purpose: purpose
  dataClassification: dataClassification
  managedBy: 'bicep'
}

var namePrefix = '${projectName}-${environmentName}'
var uniqueSuffix = substring(uniqueString(resourceGroup().id, environmentName), 0, 6)

var logAnalyticsName = 'log-${namePrefix}'
var appInsightsName = 'appi-${namePrefix}'
var managedIdentityName = 'id-${namePrefix}'
var containerAppsEnvironmentName = 'cae-${namePrefix}'
var apiContainerAppName = 'ca-${namePrefix}-api'
var webContainerAppName = 'ca-${namePrefix}-web'
var containerRegistryName = take('acr${replace(projectName, '-', '')}${environmentName}${uniqueSuffix}', 50)
var keyVaultName = take('kv-${namePrefix}-${uniqueSuffix}', 24)
var cosmosAccountName = take('cosmos-${namePrefix}-${uniqueSuffix}', 44)
var appInsightsSecretName = 'appinsights-connection-string'

module logAnalytics 'modules/log-analytics.bicep' = {
  name: 'log-analytics-deployment'
  params: {
    location: location
    name: logAnalyticsName
    tags: tags
    retentionInDays: logAnalyticsRetentionInDays
    dailyQuotaGb: logAnalyticsDailyQuotaGb
  }
}

module appInsights 'modules/app-insights.bicep' = {
  name: 'app-insights-deployment'
  params: {
    location: location
    name: appInsightsName
    tags: tags
    logAnalyticsWorkspaceId: logAnalytics.outputs.id
  }
}

module managedIdentity 'modules/managed-identity.bicep' = {
  name: 'managed-identity-deployment'
  params: {
    location: location
    name: managedIdentityName
    tags: tags
  }
}

module containerRegistry 'modules/container-registry.bicep' = {
  name: 'container-registry-deployment'
  params: {
    location: location
    name: containerRegistryName
    tags: tags
    skuName: acrSkuName
    pullPrincipalId: managedIdentity.outputs.principalId
  }
}

module keyVault 'modules/key-vault.bicep' = {
  name: 'key-vault-deployment'
  params: {
    location: location
    name: keyVaultName
    tags: tags
    enablePurgeProtection: keyVaultEnablePurgeProtection
    keyVaultAccessPrincipalId: managedIdentity.outputs.principalId
  }
}

module cosmosDb 'modules/cosmos-db.bicep' = {
  name: 'cosmos-db-deployment'
  params: {
    location: location
    accountName: cosmosAccountName
    tags: tags
    databaseName: cosmosDatabaseName
    containerName: cosmosContainerName
    partitionKeyPath: '/userId'
    consistencyLevel: cosmosConsistencyLevel
    capacityMode: cosmosCapacityMode
    throughput: cosmosThroughput
    conversationTtlSeconds: cosmosConversationTtlSeconds
    dataContributorPrincipalId: managedIdentity.outputs.principalId
  }
}

// App Insights connection string is placed in Key Vault so both Container Apps read it via a
// Key Vault reference (Managed Identity-authenticated) instead of a plain-text env var.
module appInsightsSecret 'modules/key-vault-secret.bicep' = {
  name: 'app-insights-secret-deployment'
  params: {
    keyVaultName: keyVault.outputs.name
    secretName: appInsightsSecretName
    secretValue: appInsights.outputs.connectionString
  }
}

module containerAppsEnvironment 'modules/container-apps-environment.bicep' = {
  name: 'container-apps-environment-deployment'
  params: {
    location: location
    name: containerAppsEnvironmentName
    tags: tags
    logAnalyticsCustomerId: reference(resourceId('Microsoft.OperationalInsights/workspaces', logAnalyticsName), '2022-10-01').customerId
    logAnalyticsSharedKey: listKeys(resourceId('Microsoft.OperationalInsights/workspaces', logAnalyticsName), '2022-10-01').primarySharedKey
  }
  // reference()/listKeys() above use the compile-time logAnalyticsName variable rather than
  // logAnalytics.outputs.name (required to satisfy BCP181), which means Bicep cannot infer the
  // dependency automatically — declared explicitly so the workspace exists before this deploys.
  dependsOn: [
    logAnalytics
  ]
}

module apiContainerApp 'modules/container-app.bicep' = {
  name: 'api-container-app-deployment'
  params: {
    location: location
    name: apiContainerAppName
    tags: tags
    containerAppsEnvironmentId: containerAppsEnvironment.outputs.id
    userAssignedIdentityId: managedIdentity.outputs.id
    containerRegistryLoginServer: containerRegistry.outputs.loginServer
    imageName: apiImageName
    imageTag: apiImageTag
    targetPort: 8000
    externalIngress: true
    cpuCores: apiCpuCores
    memory: apiMemory
    minReplicas: apiMinReplicas
    maxReplicas: apiMaxReplicas
    env: [
      { name: 'ENVIRONMENT', value: environmentName }
      { name: 'PROJECT_NAME', value: projectName }
      { name: 'LOG_LEVEL', value: 'INFO' }
    ]
    secrets: [
      { name: appInsightsSecretName, keyVaultUrl: appInsightsSecret.outputs.secretUri }
    ]
    secretEnvMappings: [
      { envName: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretName: appInsightsSecretName }
    ]
  }
}

// NOTE: the Web image bakes VITE_API_URL in at `docker build` time (Vite inlines VITE_* vars at
// build time, not container runtime — see docs/sprint_00/decisions.md, PBI-00-03). Setting a
// runtime env var here for the API URL would be a silent no-op, so none is set. Instead this
// template exposes apiContainerApp's FQDN as an output; the future CI/CD pipeline (PBI-00-07)
// must deploy the API Container App first, then build the Web image with
// `--build-arg VITE_API_URL=https://<apiContainerAppFqdn>`, then deploy the Web Container App.
module webContainerApp 'modules/container-app.bicep' = {
  name: 'web-container-app-deployment'
  params: {
    location: location
    name: webContainerAppName
    tags: tags
    containerAppsEnvironmentId: containerAppsEnvironment.outputs.id
    userAssignedIdentityId: managedIdentity.outputs.id
    containerRegistryLoginServer: containerRegistry.outputs.loginServer
    imageName: webImageName
    imageTag: webImageTag
    targetPort: 3000
    externalIngress: true
    cpuCores: webCpuCores
    memory: webMemory
    minReplicas: webMinReplicas
    maxReplicas: webMaxReplicas
    env: [
      { name: 'ENVIRONMENT', value: environmentName }
    ]
    secrets: [
      { name: appInsightsSecretName, keyVaultUrl: appInsightsSecret.outputs.secretUri }
    ]
    secretEnvMappings: [
      { envName: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretName: appInsightsSecretName }
    ]
  }
}

output containerRegistryName string = containerRegistry.outputs.name
output containerRegistryLoginServer string = containerRegistry.outputs.loginServer
output containerRegistryId string = containerRegistry.outputs.id

output logAnalyticsWorkspaceName string = logAnalytics.outputs.name
output logAnalyticsWorkspaceId string = logAnalytics.outputs.id

output appInsightsName string = appInsights.outputs.name
output appInsightsId string = appInsights.outputs.id

output keyVaultName string = keyVault.outputs.name
output keyVaultUri string = keyVault.outputs.uri
output keyVaultId string = keyVault.outputs.id
output keyVaultTenantId string = keyVault.outputs.tenantId

output managedIdentityName string = managedIdentity.outputs.name
output managedIdentityId string = managedIdentity.outputs.id
output managedIdentityClientId string = managedIdentity.outputs.clientId
output managedIdentityPrincipalId string = managedIdentity.outputs.principalId

output containerAppsEnvironmentName string = containerAppsEnvironment.outputs.name
output containerAppsEnvironmentId string = containerAppsEnvironment.outputs.id
output containerAppsEnvironmentDefaultDomain string = containerAppsEnvironment.outputs.defaultDomain

output apiContainerAppName string = apiContainerApp.outputs.name
output apiContainerAppId string = apiContainerApp.outputs.id
output apiContainerAppFqdn string = apiContainerApp.outputs.fqdn

output webContainerAppName string = webContainerApp.outputs.name
output webContainerAppId string = webContainerApp.outputs.id
output webContainerAppFqdn string = webContainerApp.outputs.fqdn

output cosmosAccountName string = cosmosDb.outputs.accountName
output cosmosDocumentEndpoint string = cosmosDb.outputs.documentEndpoint
output cosmosDatabaseName string = cosmosDb.outputs.databaseName
output cosmosContainerName string = cosmosDb.outputs.containerName
output cosmosAccountId string = cosmosDb.outputs.accountId

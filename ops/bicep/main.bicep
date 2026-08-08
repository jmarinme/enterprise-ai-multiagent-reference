// TMX Enterprise AI Reference Platform — Sprint 0 Bicep foundation (PBI-00-04, extended by
// PBI-00-05 with the Cosmos DB conversation store, by PBI-02-02 with an Azure AI Search service
// backing the optional AzureAISearchProvider KnowledgeProvider, by PBI-03-02 with an Azure
// OpenAI account/deployment plus the Container App environment-variable wiring that actually
// selects and points the API at these Azure-backed providers at runtime, and by PBI-03-04 with
// a production-ready VNet, Private Endpoints, and Private DNS Zones for Azure OpenAI/AI Search/
// Cosmos DB/Key Vault.
//
// Scope: Container Registry, Log Analytics, Application Insights, Container Apps environment,
// API + Web Container Apps, a shared user-assigned Managed Identity, a Key Vault foundation,
// a Cosmos DB for NoSQL conversation history store, an Azure AI Search service (service only —
// no index or document ingestion), an Azure OpenAI account with one chat-completion model
// deployment, and (opt-in via enablePrivateNetworking) a VNet with subnet separation, NSGs,
// Private Endpoints, and Private DNS Zones for all four data-plane services. Every RBAC role
// the API's Managed Identity needs against these services (Cognitive Services OpenAI User,
// Search Index Data Reader, Cosmos DB Data Contributor, Key Vault Secrets User, AcrPull) is
// wired here at least-privilege, data-plane scope only — audited in PBI-03-04, unchanged from
// PBI-03-02 (see docs/sprint_03/decisions.md).
//
// PBI-03-04 explicitly does NOT: implement Azure Front Door, Application Gateway, WAF, Azure
// Firewall, a DDoS protection plan, hub-spoke topology, VPN, or ExpressRoute — see
// docs/Architecture/adr/0002-vnet-private-endpoints-hardening.md for why each is deferred to
// its own future infrastructure PBI. PBI-03-02/03-03's own exclusions (index creation, real
// deployment) still apply unchanged.
//
// Explicitly out of scope (later PBIs/ADRs): API Management, Storage accounts, agent business
// logic, RAG index creation/ingestion, Front Door/WAF/Azure Firewall/hub-spoke/VPN/ExpressRoute.
//
// Deploys into an existing resource group supplied at deploy time (`az deployment group create
// --resource-group <rg>`) — the resource group name is intentionally never referenced here.

targetScope = 'resourceGroup'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Deployment environment. Drives conservative-vs-larger scaling and protection defaults via the parameter files, not this template.')
@allowed(['dev', 'staging', 'prod'])
param environmentName string

@description('Short, generic project identifier used to build resource names. Safe for a public academic reference repository. "tmxap" = "TMX Agent Platform" abbreviated to 5 characters — Key Vault names are capped at 24 characters (kv-{projectName}-{environmentName}-{6-char uniqueString suffix}), and with "staging" (7 chars) as the longest environmentName, projectName must be <= 6 characters or the uniqueness suffix gets silently truncated off. See docs/sprint_03/decisions.md (PBI-03-05) for the full derivation.')
param projectName string = 'tmxap'

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

@description('Azure AI Search pricing tier. Free is the conservative default for dev/academic use — sufficient for a synthetic reference-document corpus and this platform explicitly does not use semantic ranking, which Free does not support anyway.')
@allowed(['free', 'basic', 'standard'])
param aiSearchSkuName string = 'free'

@description('Azure AI Search index name AzureAISearchProvider will query. Index creation/ingestion is out of scope for PBI-03-02 — this only plumbs the name through; leave the default placeholder until a future PBI actually creates the index.')
param aiSearchIndexName string = 'tmxap-knowledge-index'

@description('Azure region for the AI Search service. Defaults to the same region as everything else (location); override only to work around a transient regional capacity shortage for new AI Search service creation (PBI-03-05 hit this in eastus2 — see docs/sprint_03/decisions.md). WARNING: if enablePrivateNetworking is true, this MUST stay equal to location — Private Endpoints live in the same VNet as the rest of the stack and cannot reach a cross-region resource without VNet peering, which this template does not provision.')
param aiSearchLocation string = location

@description('Azure OpenAI Cognitive Services pricing tier. S0 is the only tier Azure OpenAI deployments support.')
@allowed(['S0'])
param azureOpenAiSkuName string = 'S0'

@description('Azure OpenAI model deployment name — becomes AZURE_OPENAI_DEPLOYMENT on the API Container App.')
param azureOpenAiDeploymentName string = 'chat'

@description('Azure OpenAI model name to deploy. gpt-5-mini (PBI-03-05): gpt-4o-mini is lifecycle status "Deprecating" in the live Azure OpenAI model catalog and rejected for new deployments — see docs/sprint_03/decisions.md.')
param azureOpenAiModelName string = 'gpt-5-mini'

@description('Azure OpenAI model version to deploy.')
param azureOpenAiModelVersion string = '2025-08-07'

@description('Azure OpenAI deployment capacity in units of 1,000 tokens-per-minute (TPM). Conservative default sized for dev/academic use.')
@minValue(1)
param azureOpenAiModelCapacity int = 10

@description('Azure OpenAI REST API version the AzureOpenAIProvider SDK client targets.')
param azureOpenAiApiVersion string = '2024-10-21'

@description('Which LLMProvider the API Container App selects at runtime (src.config.settings.LLMSettings.llm_provider). All three Azure resources below are always provisioned regardless of this value — this only selects which one the running app actually calls.')
@allowed(['mock', 'azure_openai', 'ollama'])
param llmProvider string = 'azure_openai'

@description('Which KnowledgeProvider the API Container App selects at runtime. Defaults to "local" — NOT "azure_ai_search" — because no AI Search index exists yet (out of scope for PBI-03-02); selecting azure_ai_search before an index exists would make AzureAISearchProvider fail at startup. Flip this once a future PBI creates and populates the index. See docs/sprint_03/decisions.md.')
@allowed(['local', 'azure_ai_search'])
param knowledgeProvider string = 'local'

@description('Which ConversationRepository the API Container App selects at runtime. cosmos is safe as the default here because this template fully provisions the Cosmos database/container/RBAC — unlike the AI Search index, nothing further is required for it to work.')
@allowed(['in_memory', 'cosmos'])
param conversationStoreProvider string = 'cosmos'

@description('Production network hardening (PBI-03-04): provisions a VNet, subnet separation, NSGs, Private Endpoints, and Private DNS Zones for Azure OpenAI/AI Search/Cosmos DB/Key Vault, and disables each one\'s public endpoint. false (the default, matching dev\'s conservative-cost posture) leaves every resource exactly as PBI-03-02 shipped it — publicly reachable, RBAC-gated only. NOTE: if aiSearchSkuName is "free", this MUST stay false — Azure AI Search\'s Free tier does not support Private Link.')
param enablePrivateNetworking bool = false

@description('VNet address space. Never hardcoded — only read when enablePrivateNetworking is true.')
param vnetAddressPrefix string = '10.0.0.0/16'

@description('Container Apps Environment subnet address prefix. Must be at least /27.')
param containerAppsSubnetPrefix string = '10.0.0.0/23'

@description('Private Endpoints subnet address prefix.')
param privateEndpointsSubnetPrefix string = '10.0.2.0/24'

@description('Whether the Container Apps Environment is fully internal (no public IP) once VNet-integrated. Only meaningful when enablePrivateNetworking is true. Defaults to false: Azure Front Door/Application Gateway are out of scope for PBI-03-04, so true would make the platform completely unreachable today — see docs/Architecture/adr/0002-vnet-private-endpoints-hardening.md for the production recommendation once one exists.')
param containerAppsEnvironmentInternal bool = false

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
var aiSearchName = take('srch-${namePrefix}-${uniqueSuffix}', 60)
var azureOpenAiName = take('aoai-${namePrefix}-${uniqueSuffix}', 64)
var appInsightsSecretName = 'appinsights-connection-string'
var vnetName = 'vnet-${namePrefix}'

// Fixed Azure "privatelink.*" DNS suffixes (PBI-03-04) — global platform constants Azure
// itself defines for each service, never environment-specific data. Same category as the
// built-in RBAC role GUIDs already hardcoded as `var`s throughout ops/bicep/modules/.
var azureOpenAiPrivateDnsZoneName = 'privatelink.openai.azure.com'
var aiSearchPrivateDnsZoneName = 'privatelink.search.windows.net'
var cosmosPrivateDnsZoneName = 'privatelink.documents.azure.com'
var keyVaultPrivateDnsZoneName = 'privatelink.vaultcore.azure.net'

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

module virtualNetwork 'modules/virtual-network.bicep' = if (enablePrivateNetworking) {
  name: 'virtual-network-deployment'
  params: {
    location: location
    name: vnetName
    tags: tags
    addressPrefix: vnetAddressPrefix
    containerAppsSubnetPrefix: containerAppsSubnetPrefix
    privateEndpointsSubnetPrefix: privateEndpointsSubnetPrefix
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
    // pushPrincipalId (PBI-04-01): the CI/CD pipeline authenticates as this same Managed
    // Identity via Workload Identity Federation (no new identity, no stored credential) — see
    // docs/sprint_04/decisions.md.
    pushPrincipalId: managedIdentity.outputs.principalId
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
    enablePublicNetworkAccess: !enablePrivateNetworking
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
    enablePublicNetworkAccess: !enablePrivateNetworking
  }
}

module aiSearch 'modules/ai-search.bicep' = {
  name: 'ai-search-deployment'
  params: {
    location: aiSearchLocation
    name: aiSearchName
    tags: tags
    skuName: aiSearchSkuName
    searchIndexDataReaderPrincipalId: managedIdentity.outputs.principalId
    enablePublicNetworkAccess: !enablePrivateNetworking
  }
}

module azureOpenAi 'modules/azure-openai.bicep' = {
  name: 'azure-openai-deployment'
  params: {
    location: location
    name: azureOpenAiName
    tags: tags
    skuName: azureOpenAiSkuName
    deploymentName: azureOpenAiDeploymentName
    modelName: azureOpenAiModelName
    modelVersion: azureOpenAiModelVersion
    modelCapacity: azureOpenAiModelCapacity
    openAiUserPrincipalId: managedIdentity.outputs.principalId
    enablePublicNetworkAccess: !enablePrivateNetworking
  }
}

// Private DNS Zones (PBI-03-04) — one per service, each linked to the VNet. See
// modules/private-dns-zone.bicep's own header comment for why the zone names are fixed Azure
// platform constants (vars above), not customer-specific data requiring a parameter.
module azureOpenAiPrivateDnsZone 'modules/private-dns-zone.bicep' = if (enablePrivateNetworking) {
  name: 'azure-openai-private-dns-zone-deployment'
  params: {
    zoneName: azureOpenAiPrivateDnsZoneName
    vnetId: virtualNetwork.?outputs.?id ?? ''
    tags: tags
  }
}

module aiSearchPrivateDnsZone 'modules/private-dns-zone.bicep' = if (enablePrivateNetworking) {
  name: 'ai-search-private-dns-zone-deployment'
  params: {
    zoneName: aiSearchPrivateDnsZoneName
    vnetId: virtualNetwork.?outputs.?id ?? ''
    tags: tags
  }
}

module cosmosPrivateDnsZone 'modules/private-dns-zone.bicep' = if (enablePrivateNetworking) {
  name: 'cosmos-private-dns-zone-deployment'
  params: {
    zoneName: cosmosPrivateDnsZoneName
    vnetId: virtualNetwork.?outputs.?id ?? ''
    tags: tags
  }
}

module keyVaultPrivateDnsZone 'modules/private-dns-zone.bicep' = if (enablePrivateNetworking) {
  name: 'key-vault-private-dns-zone-deployment'
  params: {
    zoneName: keyVaultPrivateDnsZoneName
    vnetId: virtualNetwork.?outputs.?id ?? ''
    tags: tags
  }
}

// Private Endpoints (PBI-03-04) — one per service, in the private-endpoints subnet, each
// registered in its own Private DNS Zone so the platform's existing DefaultAzureCredential
// clients (AzureOpenAIProvider, AzureAISearchProvider, CosmosConversationRepository) resolve
// straight to the private IP with zero code change.
module azureOpenAiPrivateEndpoint 'modules/private-endpoint.bicep' = if (enablePrivateNetworking) {
  name: 'azure-openai-private-endpoint-deployment'
  params: {
    location: location
    name: 'pe-${azureOpenAiName}'
    tags: tags
    subnetId: virtualNetwork.?outputs.?privateEndpointsSubnetId ?? ''
    targetResourceId: azureOpenAi.outputs.id
    groupId: 'account'
    privateDnsZoneId: azureOpenAiPrivateDnsZone.?outputs.?id ?? ''
  }
}

module aiSearchPrivateEndpoint 'modules/private-endpoint.bicep' = if (enablePrivateNetworking) {
  name: 'ai-search-private-endpoint-deployment'
  params: {
    location: location
    name: 'pe-${aiSearchName}'
    tags: tags
    subnetId: virtualNetwork.?outputs.?privateEndpointsSubnetId ?? ''
    targetResourceId: aiSearch.outputs.id
    groupId: 'searchService'
    privateDnsZoneId: aiSearchPrivateDnsZone.?outputs.?id ?? ''
  }
}

module cosmosPrivateEndpoint 'modules/private-endpoint.bicep' = if (enablePrivateNetworking) {
  name: 'cosmos-private-endpoint-deployment'
  params: {
    location: location
    name: 'pe-${cosmosAccountName}'
    tags: tags
    subnetId: virtualNetwork.?outputs.?privateEndpointsSubnetId ?? ''
    targetResourceId: cosmosDb.outputs.accountId
    groupId: 'Sql'
    privateDnsZoneId: cosmosPrivateDnsZone.?outputs.?id ?? ''
  }
}

module keyVaultPrivateEndpoint 'modules/private-endpoint.bicep' = if (enablePrivateNetworking) {
  name: 'key-vault-private-endpoint-deployment'
  params: {
    location: location
    name: 'pe-${keyVaultName}'
    tags: tags
    subnetId: virtualNetwork.?outputs.?privateEndpointsSubnetId ?? ''
    targetResourceId: keyVault.outputs.id
    groupId: 'vault'
    privateDnsZoneId: keyVaultPrivateDnsZone.?outputs.?id ?? ''
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
    infrastructureSubnetId: virtualNetwork.?outputs.?containerAppsSubnetId ?? ''
    internal: containerAppsEnvironmentInternal
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
    // cicdPrincipalId (PBI-04-01): grants the same Managed Identity the CI/CD pipeline
    // authenticates as (via Workload Identity Federation) permission to update this specific
    // Container App's image/revision — see docs/sprint_04/decisions.md.
    cicdPrincipalId: managedIdentity.outputs.principalId
    env: [
      { name: 'ENVIRONMENT', value: environmentName }
      { name: 'PROJECT_NAME', value: projectName }
      { name: 'LOG_LEVEL', value: 'INFO' }
      // AZURE_CLIENT_ID (PBI-03-05): required so DefaultAzureCredential's ManagedIdentityCredential
      // component knows which identity to use. A user-assigned identity is ambiguous to
      // DefaultAzureCredential without this — confirmed via a real deployment failure ("Unable to
      // load the proper Managed Identity"). See docs/sprint_03/decisions.md.
      { name: 'AZURE_CLIENT_ID', value: managedIdentity.outputs.clientId }
      // Provider selection (PBI-03-02): every Azure resource below is always provisioned by
      // this template regardless of these values — they only tell the running app which one
      // to actually call. See the llmProvider/knowledgeProvider/conversationStoreProvider
      // param descriptions above for why knowledgeProvider defaults to 'local'.
      { name: 'LLM_PROVIDER', value: llmProvider }
      { name: 'KNOWLEDGE_PROVIDER', value: knowledgeProvider }
      { name: 'CONVERSATION_STORE_PROVIDER', value: conversationStoreProvider }
      // Azure OpenAI — Managed Identity is the default auth path (AZURE_OPENAI_USE_API_KEY
      // stays false); no API key is ever placed in a Container App env var.
      { name: 'AZURE_OPENAI_ENDPOINT', value: azureOpenAi.outputs.endpoint }
      { name: 'AZURE_OPENAI_DEPLOYMENT', value: azureOpenAi.outputs.deploymentName }
      // AZURE_OPENAI_MODEL_NAME (PBI-03-05): the underlying model, distinct from the deployment
      // alias above — AzureOpenAIProvider needs this to detect reasoning-family model capability
      // differences (e.g. gpt-5-mini rejecting a non-default temperature). See
      // src/llm/azure_openai_provider.py and docs/sprint_03/decisions.md.
      { name: 'AZURE_OPENAI_MODEL_NAME', value: azureOpenAi.outputs.modelName }
      { name: 'AZURE_OPENAI_API_VERSION', value: azureOpenAiApiVersion }
      { name: 'AZURE_OPENAI_USE_API_KEY', value: 'false' }
      // Azure AI Search — same Managed-Identity-default posture.
      { name: 'AZURE_AI_SEARCH_ENDPOINT', value: aiSearch.outputs.endpoint }
      { name: 'AZURE_AI_SEARCH_INDEX_NAME', value: aiSearchIndexName }
      { name: 'AZURE_AI_SEARCH_USE_API_KEY', value: 'false' }
      // Cosmos DB — endpoint only; disableLocalAuth=true on the account means no connection
      // string exists to leak (see ops/bicep/modules/cosmos-db.bicep).
      { name: 'COSMOS_DB_ENDPOINT', value: cosmosDb.outputs.documentEndpoint }
      { name: 'COSMOS_DB_DATABASE', value: cosmosDb.outputs.databaseName }
      { name: 'COSMOS_DB_CONTAINER', value: cosmosDb.outputs.containerName }
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
    // cicdPrincipalId (PBI-04-01): same rationale as apiContainerApp above.
    cicdPrincipalId: managedIdentity.outputs.principalId
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

output aiSearchName string = aiSearch.outputs.name
output aiSearchEndpoint string = aiSearch.outputs.endpoint
output aiSearchId string = aiSearch.outputs.id

output azureOpenAiName string = azureOpenAi.outputs.name
output azureOpenAiEndpoint string = azureOpenAi.outputs.endpoint
output azureOpenAiDeploymentName string = azureOpenAi.outputs.deploymentName
output azureOpenAiId string = azureOpenAi.outputs.id

output privateNetworkingEnabled bool = enablePrivateNetworking
output vnetId string = virtualNetwork.?outputs.?id ?? ''
output vnetName string = virtualNetwork.?outputs.?name ?? ''
output containerAppsSubnetId string = virtualNetwork.?outputs.?containerAppsSubnetId ?? ''
output privateEndpointsSubnetId string = virtualNetwork.?outputs.?privateEndpointsSubnetId ?? ''

output azureOpenAiPrivateEndpointId string = azureOpenAiPrivateEndpoint.?outputs.?id ?? ''
output aiSearchPrivateEndpointId string = aiSearchPrivateEndpoint.?outputs.?id ?? ''
output cosmosPrivateEndpointId string = cosmosPrivateEndpoint.?outputs.?id ?? ''
output keyVaultPrivateEndpointId string = keyVaultPrivateEndpoint.?outputs.?id ?? ''

output azureOpenAiPrivateDnsZoneId string = azureOpenAiPrivateDnsZone.?outputs.?id ?? ''
output aiSearchPrivateDnsZoneId string = aiSearchPrivateDnsZone.?outputs.?id ?? ''
output cosmosPrivateDnsZoneId string = cosmosPrivateDnsZone.?outputs.?id ?? ''
output keyVaultPrivateDnsZoneId string = keyVaultPrivateDnsZone.?outputs.?id ?? ''

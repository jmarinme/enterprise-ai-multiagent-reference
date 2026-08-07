using '../main.bicep'

// Prod: more headroom and longer log retention; purge protection on.
// NOTE: CLAUDE.md out-of-scope items (RAG index/ingestion, real integrations, automatic prod
// deployment) still apply — this parameter file describes infrastructure shape only, not an
// authorization to deploy.

param environmentName = 'prod'
param projectName = 'tmxai'
param purpose = 'academic-reference-platform'
param dataClassification = 'synthetic'

param acrSkuName = 'Standard'
param logAnalyticsRetentionInDays = 90
param logAnalyticsDailyQuotaGb = -1
param keyVaultEnablePurgeProtection = true

param cosmosDatabaseName = 'tmxai-conversation-db'
param cosmosContainerName = 'conversations'
param cosmosConsistencyLevel = 'Session'
param cosmosCapacityMode = 'Provisioned'
param cosmosThroughput = 400
param cosmosConversationTtlSeconds = -1

param aiSearchSkuName = 'basic'
param aiSearchIndexName = 'tmxai-knowledge-index'

param azureOpenAiSkuName = 'S0'
param azureOpenAiDeploymentName = 'chat'
param azureOpenAiModelName = 'gpt-4o-mini'
param azureOpenAiModelVersion = '2024-07-18'
param azureOpenAiModelCapacity = 50
param azureOpenAiApiVersion = '2024-10-21'

// Provider selection (PBI-03-02): knowledgeProvider stays 'local' — see dev.bicepparam and
// docs/sprint_03/decisions.md; no AI Search index exists yet in any environment.
param llmProvider = 'azure_openai'
param knowledgeProvider = 'local'
param conversationStoreProvider = 'cosmos'

param apiImageName = 'tmx-api'
param apiImageTag = 'pending-first-build'
param apiCpuCores = '0.5'
param apiMemory = '1Gi'
param apiMinReplicas = 2
param apiMaxReplicas = 5

param webImageName = 'tmx-web'
param webImageTag = 'pending-first-build'
param webCpuCores = '0.5'
param webMemory = '1Gi'
param webMinReplicas = 2
param webMaxReplicas = 5

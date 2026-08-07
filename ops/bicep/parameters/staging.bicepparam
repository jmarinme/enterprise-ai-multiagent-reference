using '../main.bicep'

// Staging: modest headroom for pre-production validation; purge protection on.

param environmentName = 'staging'
param projectName = 'tmxai'
param purpose = 'academic-reference-platform'
param dataClassification = 'synthetic'

param acrSkuName = 'Standard'
param logAnalyticsRetentionInDays = 30
param logAnalyticsDailyQuotaGb = -1
param keyVaultEnablePurgeProtection = true

param cosmosDatabaseName = 'tmxai-conversation-db'
param cosmosContainerName = 'conversations'
param cosmosConsistencyLevel = 'Session'
param cosmosCapacityMode = 'Serverless'
param cosmosConversationTtlSeconds = -1

// Basic (not Free): staging is not the single free-tier slot a subscription gets, and an SLA
// is appropriate for pre-production validation.
param aiSearchSkuName = 'basic'
param aiSearchIndexName = 'tmxai-knowledge-index'

param azureOpenAiSkuName = 'S0'
param azureOpenAiDeploymentName = 'chat'
param azureOpenAiModelName = 'gpt-4o-mini'
param azureOpenAiModelVersion = '2024-07-18'
param azureOpenAiModelCapacity = 30
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
param apiMinReplicas = 1
param apiMaxReplicas = 2

param webImageName = 'tmx-web'
param webImageTag = 'pending-first-build'
param webCpuCores = '0.5'
param webMemory = '1Gi'
param webMinReplicas = 1
param webMaxReplicas = 2

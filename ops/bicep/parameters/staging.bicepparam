using '../main.bicep'

// Staging: modest headroom for pre-production validation; purge protection on.

param environmentName = 'staging'
param projectName = 'tmxap'
param purpose = 'academic-reference-platform'
param dataClassification = 'synthetic'

param acrSkuName = 'Standard'
param logAnalyticsRetentionInDays = 30
param logAnalyticsDailyQuotaGb = -1
param keyVaultEnablePurgeProtection = true

param cosmosDatabaseName = 'tmxap-conversation-db'
param cosmosContainerName = 'conversations'
param cosmosConsistencyLevel = 'Session'
param cosmosCapacityMode = 'Serverless'
param cosmosConversationTtlSeconds = -1

// Basic (not Free): staging is not the single free-tier slot a subscription gets, and an SLA
// is appropriate for pre-production validation.
param aiSearchSkuName = 'basic'
param aiSearchIndexName = 'tmxap-knowledge-index'

param azureOpenAiSkuName = 'S0'
param azureOpenAiDeploymentName = 'chat'
// gpt-5-mini replaces gpt-4o-mini as of PBI-03-05 — see dev.bicepparam and
// docs/sprint_03/decisions.md for the full rationale.
param azureOpenAiModelName = 'gpt-5-mini'
param azureOpenAiModelVersion = '2025-08-07'
param azureOpenAiModelCapacity = 30
param azureOpenAiApiVersion = '2024-10-21'

// Provider selection (PBI-03-02): knowledgeProvider stays 'local' — see dev.bicepparam and
// docs/sprint_03/decisions.md; no AI Search index exists yet in any environment.
param llmProvider = 'azure_openai'
param knowledgeProvider = 'local'
param conversationStoreProvider = 'cosmos'

// Networking (PBI-03-04): enabled — staging validates the same hardened network posture prod
// will run, matching this file's own "modest headroom for pre-production validation" purpose.
// containerAppsEnvironmentInternal stays false (the main.bicep default): Azure Front
// Door/Application Gateway are out of scope for PBI-03-04, so true would make staging
// unreachable. See docs/Architecture/adr/0002-vnet-private-endpoints-hardening.md.
param enablePrivateNetworking = true
param vnetAddressPrefix = '10.1.0.0/16'
param containerAppsSubnetPrefix = '10.1.0.0/23'
param privateEndpointsSubnetPrefix = '10.1.2.0/24'

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

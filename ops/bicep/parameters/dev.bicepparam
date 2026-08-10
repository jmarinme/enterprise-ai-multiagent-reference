using '../main.bicep'

// Dev: conservative, single-replica, low-cost, easy to tear down (no Key Vault purge protection).

param environmentName = 'dev'
param projectName = 'tmxap'
param purpose = 'academic-reference-platform'
param dataClassification = 'synthetic'

param acrSkuName = 'Basic'
param logAnalyticsRetentionInDays = 30
param logAnalyticsDailyQuotaGb = 1
param keyVaultEnablePurgeProtection = false

param cosmosDatabaseName = 'tmxap-conversation-db'
param cosmosContainerName = 'conversations'
param cosmosConsistencyLevel = 'Session'
param cosmosCapacityMode = 'Serverless'
param cosmosConversationTtlSeconds = -1

param aiSearchSkuName = 'free'
param aiSearchIndexName = 'tmxap-knowledge-index'
// eastus, not eastus2: PBI-03-05's real deployment hit "InsufficientResourcesAvailable" twice
// creating a new AI Search service in eastus2. Safe here because enablePrivateNetworking stays
// false in this file (see main.bicep's aiSearchLocation warning) — see docs/sprint_03/decisions.md.
param aiSearchLocation = 'eastus'

param azureOpenAiSkuName = 'S0'
param azureOpenAiDeploymentName = 'chat'
// gpt-5-mini replaces gpt-4o-mini as of PBI-03-05: a real deployment against the live Azure
// OpenAI model catalog (Microsoft.CognitiveServices /locations/eastus2/models) showed
// gpt-4o-mini:2024-07-18 is lifecycle status "Deprecating" and rejected for new deployments.
// gpt-5-mini (2025-08-07) is the current GenerallyAvailable same-tier successor. See
// docs/sprint_03/decisions.md (PBI-03-05).
param azureOpenAiModelName = 'gpt-5-mini'
param azureOpenAiModelVersion = '2025-08-07'
param azureOpenAiModelCapacity = 10
param azureOpenAiApiVersion = '2024-10-21'

// Provider selection (PBI-03-02): knowledgeProvider stays 'local' even in the Azure dev
// environment — no AI Search index exists yet (out of scope), and azure_ai_search would make
// AzureAISearchProvider fail at startup. See docs/sprint_03/decisions.md.
param llmProvider = 'azure_openai'
param knowledgeProvider = 'local'
param conversationStoreProvider = 'cosmos'

// Networking (PBI-03-04): disabled for dev — matches the same conservative-cost posture
// already applied to Free-tier AI Search and Serverless Cosmos above. A disposable dev
// sandbox does not need VNet/Private Endpoint planning; every resource stays publicly
// reachable, RBAC-gated only, exactly as PBI-03-02 shipped it. See docs/sprint_03/decisions.md.
param enablePrivateNetworking = false

// Placeholder tags — a real deployment requires an image already pushed to the registry created
// by this template. CI/CD (PBI-00-07) is responsible for building and pushing before deploying.
param apiImageName = 'tmx-api'
param apiImageTag = 'pending-first-build'
param apiCpuCores = '0.25'
param apiMemory = '0.5Gi'
param apiMinReplicas = 1
param apiMaxReplicas = 1

param webImageName = 'tmx-web'
param webImageTag = 'pending-first-build'
param webCpuCores = '0.25'
param webMemory = '0.5Gi'
param webMinReplicas = 1
param webMaxReplicas = 1

// PBI-06-01: Claims Tool Layer / Durable Functions Function App. P0v4 (Premium v4), not Y1
// (Consumption) or B1 (Basic): real deployment attempts on 2026-08-09/10 reported
// SubscriptionIsOverQuotaForSku (0 quota, "Total Regional VMs" limit 0) for BOTH Y1 and B1 —
// this subscription has 0 quota across every classic App Service compute family (Free, Shared,
// Basic, Standard, PremiumV2/V3, Isolated v2, Elastic Premium) in every region checked. A live
// requery of Microsoft.Web/locations/{region}/usages (PBI-06-01A) found nonzero quota (30) for
// the newer Premium v4 family (P0v4-P3v4) in eastus2/eastus specifically. P0v4 is a DEV-ONLY
// workaround approved for PBI-06-01A, not the production hosting recommendation — see
// docs/Architecture/adr/0003-azure-functions-tool-and-workflow-layer.md and
// docs/sprint_06/decisions.md.
param functionAppPlanSkuName = 'P0v4'
param toolProvider = 'inprocess'
param claimsWorkflowProvider = 'inprocess'

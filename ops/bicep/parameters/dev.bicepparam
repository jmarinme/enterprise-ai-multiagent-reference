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

// PBI-08-01A: Claims Tool Layer / Durable Functions Function App deployment is DISABLED in DEV.
// This subscription has 0 Microsoft.Web (App Service) quota in every region checked, for every
// SKU tried — 3 independent real `az deployment group create` attempts (Y1/Consumption,
// B1/Basic, P0v4/Premium v4) all failed with SubscriptionIsOverQuotaForSku (see
// docs/Architecture/adr/0003-azure-functions-tool-and-workflow-layer.md and
// docs/sprint_06/decisions.md D-07, docs/sprint_07/decisions.md PBI-07-01B). Rather than keep
// attempting (and failing) a Function App deployment on every pipeline run, PBI-08-01A gated
// the Function App/App Service Plan/dedicated Storage Account behind deployServerlessToolLayer
// — false here means DEV deploys none of them at all. The application code, the Bicep module,
// and the ToolProvider/ClaimsWorkflowProvider abstractions that would call it all remain fully
// in place (CLAUDE.md §4.1/§4.2, ADR-0003 — serverless stays the target architecture); setting
// this to true (once quota is granted) is the only change required to actually deploy it — no
// redesign. functionAppPlanSkuName stays 'P0v4' as the value to use WHEN this is re-enabled
// (still the best-evidenced SKU for this subscription's actual quota shape), not because it
// does anything while deployServerlessToolLayer is false.
param deployServerlessToolLayer = false
param functionAppPlanSkuName = 'P0v4'
// DEV's actual, current runtime configuration — unaffected by deployServerlessToolLayer, and
// deliberately left at "inprocess" per PBI-08-01A's own explicit instruction. Flipping either
// to azure_functions/durable only makes sense once deployServerlessToolLayer=true has actually
// provisioned the Function App these would call.
param toolProvider = 'inprocess'
param claimsWorkflowProvider = 'inprocess'

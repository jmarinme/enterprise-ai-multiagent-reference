using '../main.bicep'

// Dev: conservative, single-replica, low-cost, easy to tear down (no Key Vault purge protection).

param environmentName = 'dev'
param projectName = 'tmxai'
param purpose = 'academic-reference-platform'
param dataClassification = 'synthetic'

param acrSkuName = 'Basic'
param logAnalyticsRetentionInDays = 30
param logAnalyticsDailyQuotaGb = 1
param keyVaultEnablePurgeProtection = false

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

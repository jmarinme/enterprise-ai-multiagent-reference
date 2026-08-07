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

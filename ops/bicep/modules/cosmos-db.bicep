// Azure Cosmos DB for NoSQL — conversation history store (CLAUDE.md §4.3).
// Single container, partition key /userId: conversations are documents with an embedded,
// ordered messages array, so "all conversations for a user" is a single-partition query and
// "all messages in one conversation" is a point read (id + partition key) — no second
// container or round-trip needed. Core business data (policies, claims, payments, commissions)
// must never be stored here — this module intentionally has no such schema.
//
// disableLocalAuth=true: key-based auth is disabled at the account level. Access is exclusively
// via Azure AD identities (Managed Identity in Azure, developer identity locally) granted the
// built-in Cosmos DB "Data Contributor" data-plane role — no connection strings anywhere.

@description('Azure region for the Cosmos DB account.')
param location string

@description('Cosmos DB account name. Must be globally unique, lowercase alphanumeric/hyphen, 3-44 characters.')
param accountName string

@description('Resource tags applied for project, environment, purpose, data classification, and ownership traceability.')
param tags object

@description('SQL API database name.')
param databaseName string = 'tmxai-conversation-db'

@description('Conversation container name.')
param containerName string = 'conversations'

@description('Partition key path. Conversations are partitioned by synthetic user for efficient per-user retrieval.')
param partitionKeyPath string = '/userId'

@description('Cosmos DB consistency level.')
@allowed(['Eventual', 'ConsistentPrefix', 'Session', 'BoundedStaleness', 'Strong'])
param consistencyLevel string = 'Session'

@description('Capacity mode. Serverless avoids paying for idle RU/s (conservative default for dev/academic use); Provisioned gives predictable throughput.')
@allowed(['Serverless', 'Provisioned'])
param capacityMode string = 'Serverless'

@description('Manual throughput (RU/s), used only when capacityMode is Provisioned.')
@minValue(400)
param throughput int = 400

@description('Container default TTL in seconds. -1 provisions TTL support without expiring anything by default; a real retention value requires its own ADR before being set.')
param conversationTtlSeconds int = -1

@description('Principal ID of the identity granted the built-in Cosmos DB "Data Contributor" data-plane role. Empty string skips the role assignment.')
param dataContributorPrincipalId string = ''

var cosmosDataContributorRoleId = '00000000-0000-0000-0000-000000000002'

resource account 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: accountName
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: consistencyLevel
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    capabilities: capacityMode == 'Serverless' ? [
      {
        name: 'EnableServerless'
      }
    ] : []
    // Periodic backup is Cosmos's cost-effective default, appropriate for this conservative
    // dev/academic scope; Continuous backup was not requested and would add cost. Revisit via
    // ADR if a future PBI needs point-in-time restore.
    backupPolicy: {
      type: 'Periodic'
    }
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: account
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

resource container 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: containerName
  properties: {
    resource: {
      id: containerName
      partitionKey: {
        paths: [
          partitionKeyPath
        ]
        kind: 'Hash'
      }
      defaultTtl: conversationTtlSeconds
    }
    options: {
      throughput: capacityMode == 'Provisioned' ? throughput : null
    }
  }
}

resource dataContributorRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = if (!empty(dataContributorPrincipalId)) {
  parent: account
  name: guid(account.id, dataContributorPrincipalId, cosmosDataContributorRoleId)
  properties: {
    roleDefinitionId: '${account.id}/sqlRoleDefinitions/${cosmosDataContributorRoleId}'
    principalId: dataContributorPrincipalId
    scope: account.id
  }
}

output accountName string = account.name
output documentEndpoint string = account.properties.documentEndpoint
output databaseName string = database.name
output containerName string = container.name
output accountId string = account.id

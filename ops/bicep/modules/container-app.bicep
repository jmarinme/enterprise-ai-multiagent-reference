// Generic, reusable Azure Container App module. Instantiated once per application (API, Web)
// from main.bicep so the two apps share one definition instead of duplicated resource blocks.
// Pulls images via the shared user-assigned Managed Identity (no registry credentials) and
// reads Key Vault-backed secrets via Key Vault references using the same identity
// (CLAUDE.md §4.5: prefer Managed Identity and Key Vault references over embedded credentials).

@description('Azure region for the Container App.')
param location string

@description('Container App resource name.')
param name string

@description('Resource tags applied for project, environment, purpose, data classification, and ownership traceability.')
param tags object

@description('Resource ID of the Container Apps managed environment this app runs in.')
param containerAppsEnvironmentId string

@description('Resource ID of the user-assigned managed identity used for ACR pull and Key Vault secret access.')
param userAssignedIdentityId string

@description('Login server of the Azure Container Registry hosting the image (e.g. myregistry.azurecr.io).')
param containerRegistryLoginServer string

@description('Image repository name inside the registry (e.g. tmx-api).')
param imageName string

@description('Image tag to deploy. Must be supplied per environment; never defaulted here.')
param imageTag string

@description('Port the container listens on.')
param targetPort int

@description('Whether ingress is reachable from outside the Container Apps environment.')
param externalIngress bool = true

@description('CPU cores allocated to the container, e.g. 0.25.')
param cpuCores string = '0.25'

@description('Memory allocated to the container, e.g. 0.5Gi.')
param memory string = '0.5Gi'

@description('Minimum replica count.')
@minValue(0)
param minReplicas int = 1

@description('Maximum replica count.')
@minValue(1)
param maxReplicas int = 1

@description('Plain (non-secret) environment variables as { name, value } objects.')
param env array = []

@description('Key Vault-backed secrets as { name, keyVaultUrl } objects. Secret names must be Container Apps-safe (lowercase alphanumeric/hyphen).')
param secrets array = []

@description('Maps environment variable names to a secret defined in secrets, as { envName, secretName } objects. Kept separate from secrets because env var naming conventions (UPPER_SNAKE_CASE) differ from Container Apps secret-name constraints (lowercase-hyphen).')
param secretEnvMappings array = []

@description('Principal ID of the identity granted the built-in "Container Apps Contributor" role on this specific Container App — needed by the CI/CD pipeline to update the deployed image/revision (PBI-04-01). Empty string skips the role assignment. Scoped to this one Container App only, not the resource group, so the pipeline identity cannot touch Cosmos DB/Key Vault/Azure OpenAI/AI Search/the registry\'s own management plane or the other Container App via this role.')
param cicdPrincipalId string = ''

var containerAppsContributorRoleId = '358470bc-b998-42bd-ab17-a7e34c199c0f'

var secretDefinitions = [
  for s in secrets: {
    name: s.name
    keyVaultUrl: s.keyVaultUrl
    identity: userAssignedIdentityId
  }
]

var secretEnv = [
  for mapping in secretEnvMappings: {
    name: mapping.envName
    secretRef: mapping.secretName
  }
]

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${userAssignedIdentityId}': {}
    }
  }
  properties: {
    environmentId: containerAppsEnvironmentId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: externalIngress
        targetPort: targetPort
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: containerRegistryLoginServer
          identity: userAssignedIdentityId
        }
      ]
      secrets: secretDefinitions
    }
    template: {
      containers: [
        {
          name: name
          image: '${containerRegistryLoginServer}/${imageName}:${imageTag}'
          resources: {
            cpu: json(cpuCores)
            memory: memory
          }
          env: concat(env, secretEnv)
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
      }
    }
  }
}

resource cicdRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(cicdPrincipalId)) {
  name: guid(containerApp.id, cicdPrincipalId, containerAppsContributorRoleId)
  scope: containerApp
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      containerAppsContributorRoleId
    )
    principalId: cicdPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output id string = containerApp.id
output name string = containerApp.name
output fqdn string = containerApp.properties.configuration.ingress.fqdn

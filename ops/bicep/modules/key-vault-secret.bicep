// Generic module that writes a single secret into an existing Key Vault.
// Kept separate/reusable so any future module (Cosmos, Azure OpenAI, etc.) can seed a
// Key Vault secret without duplicating this resource definition.

@description('Name of the existing Key Vault to write the secret into.')
param keyVaultName string

@description('Secret name.')
param secretName string

@secure()
@description('Secret value. Marked @secure() so it is not echoed in deployment logs.')
param secretValue string

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource secret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: secretName
  properties: {
    value: secretValue
  }
}

output secretUri string = secret.properties.secretUri
output secretName string = secret.name

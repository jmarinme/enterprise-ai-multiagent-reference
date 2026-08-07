# Sprint 00 Security Baseline — Identity, Secrets, and RBAC

Companion to `docs/sprint_00/decisions.md`. Covers PBI-00-06's identity model, secret-management
model, RBAC model, and authentication for local developers, Azure Container Apps, and (future)
Azure DevOps pipelines. This is a Sprint 0 foundation document, not a full security review
(PBI-00-05's Sprint 05 "Hardening" scope per `CLAUDE.md` §14 covers that).

## 1. Identity model

A single **user-assigned Managed Identity** (`ops/bicep/modules/managed-identity.bicep`) is shared
by both Container Apps (API, Web). It is granted exactly three, minimum, built-in RBAC roles:

| Role | Scope | Granted by | Purpose |
|---|---|---|---|
| `AcrPull` | Container Registry | `container-registry.bicep` | Pull images without registry credentials |
| Key Vault "Secrets User" | Key Vault | `key-vault.bicep` | Read Key Vault-referenced secrets (e.g. App Insights connection string) |
| Cosmos DB "Data Contributor" | Cosmos account | `cosmos-db.bicep` | Read/write conversation documents, no account keys |

No other identity exists in this platform yet. No service principal client secrets, no shared
access keys, no connection strings are stored anywhere in this repository.

## 2. Secret-management model

A `SecretProvider` Protocol (`src/domain/secret_provider.py`) with two adapters
(`src/services/secret_store/`), selected via `SECRET_PROVIDER` config (default `environment`):

- `EnvironmentSecretProvider` — reads process environment variables. Default for local
  development and all unit tests; requires no Azure connectivity.
- `AzureKeyVaultSecretProvider` — reads Azure Key Vault via `DefaultAzureCredential` (async).
  Used only when `SECRET_PROVIDER=key_vault` and `KEY_VAULT_URI` is set.

Both raise a typed `SecretNotFoundError` (never `None`, never a bare `KeyError`) when a secret is
absent, so callers can handle "not configured" explicitly.

**No real secret values exist in this codebase.** This PBI prepares the *mechanism* and a naming
convention for secrets a future PBI will populate — it does not create any.

### Reserved secret-name convention (documented, not created)

Key Vault secret names use lowercase-hyphen form; `EnvironmentSecretProvider` maps them to the
equivalent `UPPER_SNAKE_CASE` environment variable. Names reserved for future use:

| Key Vault secret name | Local env var equivalent | Future consumer |
|---|---|---|
| `azure-openai-api-key` | `AZURE_OPENAI_API_KEY` | Azure OpenAI integration (out of scope until an agent PBI needs it) |
| `appinsights-connection-string` | n/a (Container Apps only) | Already created by PBI-00-04's `key-vault-secret.bicep`, since it is generated infrastructure output, not an external credential |

No Bicep resource creates the `azure-openai-api-key` secret. When a future PBI needs it, use the
existing generic `ops/bicep/modules/key-vault-secret.bicep` module to write the real value
(sourced from a secure parameter or an external secret store — never a literal in source control).

## 3. RBAC model

Key Vault uses **RBAC authorization only** (`enableRbacAuthorization: true`); it has no access
policies. All role assignments in this platform are scoped to the specific resource (vault,
registry, or Cosmos account) they grant access to — never subscription- or resource-group-wide —
and granted to the one shared Managed Identity, not to individual users or broad groups.

## 4. Authentication — local developers

Local development uses `SECRET_PROVIDER=environment` (and `CONVERSATION_STORE_PROVIDER=in_memory`
from PBI-00-05): no Azure login, no Managed Identity, no Key Vault access is required to run the
API, Web app, or test suites. `.env.example` documents every variable a developer may set; no
value in it is a real credential.

If a developer needs to test against a real Key Vault (`SECRET_PROVIDER=key_vault`) or Cosmos
account, `DefaultAzureCredential` will fall back to their own signed-in Azure CLI/developer
identity (`az login`), which must be separately granted the same minimum roles listed in §1 —
never a shared service credential.

## 5. Authentication — Azure Container Apps

Already implemented in `ops/bicep/modules/container-app.bicep` (PBI-00-04, reviewed and confirmed
unchanged by this PBI): each Container App is assigned the shared user-assigned identity
(`identity: { type: 'UserAssigned', ... }`), used both for ACR image pulls
(`configuration.registries[].identity`) and for Key Vault secret references
(`configuration.secrets[].identity`). No credentials are baked into container images or set as
plain environment variables.

## 6. Authentication — future Azure DevOps pipelines (not implemented; PBI-00-07 scope)

Recommended pattern for PBI-00-07: **Workload Identity Federation (OIDC)** between the Azure
DevOps service connection and this platform's existing user-assigned Managed Identity
(`clientId` output already exposed by `managed-identity.bicep` and `main.bicep`). This requires no
stored pipeline secret (no client secret, no publish profile, no service principal password) —
Azure DevOps exchanges a short-lived OIDC token for an Azure AD token at pipeline run time. Do not
introduce a service principal client secret as an alternative; if OIDC is not immediately
available, treat that as a blocker to raise, not a reason to fall back to a stored secret.

## 7. Entra ID end-user authentication — explicitly out of scope

This PBI, and Sprint 0 as a whole, does **not** implement end-user login (Entra ID OAuth2/OIDC for
human users of the Web app, per `CLAUDE.md` §4.5's "Frontend: Microsoft Entra ID" requirement).
The Web application has no login screen and the API performs no end-user token validation. This is
an explicit, deliberate scope boundary for the academic MVP, not an oversight — end-user
authentication is deferred to a later, dedicated PBI once the Supervisor Agent and Conversation
API (Sprint 01) exist for it to protect.

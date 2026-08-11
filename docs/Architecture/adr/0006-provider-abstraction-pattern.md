# ADR-0006: Provider Abstraction Pattern — Interfaces, Factories, and a Single Composition Root

## Status

Accepted — retroactively documented 2026-08-10 (PBI-10-02). This pattern has been implemented
since Sprint 01 (`ConversationRepository`) and extended in every subsequent sprint
(`LLMProvider` — Sprint 03; `KnowledgeProvider` — Sprint 03; `SecretProvider` — Sprint 03;
`ToolProvider`/`ClaimsWorkflowProvider` — Sprint 06, [ADR-0003](0003-azure-functions-tool-and-workflow-layer.md)).
This ADR is the first formal record of the *pattern itself* — ADR-0003 documents two concrete
instances of it (`ToolProvider`, `ClaimsWorkflowProvider`) but not the general architecture every
other provider in the platform already follows.

## Context

Every external dependency this platform relies on — the LLM, the conversation store, the RAG
knowledge source, the secret store, the Claims Tool execution backend, and the Claims workflow
execution backend — has at least two real implementations in the repository today: a
zero-dependency local/test double and an Azure-backed production implementation. CLAUDE.md's own
architecture principles require this: agents must never hold a concrete dependency on "Azure
OpenAI" or "Cosmos DB" directly, both to keep local development/tests free of live Azure
connectivity, and so that swapping a backend (e.g., `inprocess` → `azure_functions`, per
[ADR-0003](0003-azure-functions-tool-and-workflow-layer.md)) never touches Agent or business
logic.

## Decision

Every external dependency is expressed as a `typing.Protocol` interface, with one or more
concrete implementations selected at process-startup time by a small, dedicated factory function,
itself driven by a `pydantic_settings.BaseSettings` class. Exactly one module,
`apps/api/src/api/dependencies.py`, imports every concrete implementation and wires them together
— it is the platform's single composition root.

### Provider interfaces (Protocols, never concrete classes, in Agent/business-logic signatures)

| Provider | Protocol location | Implementations |
|---|---|---|
| `LLMProvider` | `src/llm/provider.py` | `MockLLMProvider`, `AzureOpenAIProvider`, `OllamaProvider` (`src/llm/`) |
| `ConversationRepository` | `src/domain/conversation_repository.py` | `InMemoryConversationRepository`, `CosmosConversationRepository` ([ADR-0004](0004-conversation-store-selection.md)) |
| `KnowledgeProvider` | `src/rag/provider.py` | `LocalKnowledgeProvider`, `AzureAISearchProvider` (`src/rag/`) |
| `SecretProvider` | `src/domain/secret_provider.py` | `EnvironmentSecretProvider`, `KeyVaultSecretProvider` (`src/services/secret_store/`) |
| `ToolProvider` | `src/core/tool_provider/protocol.py` | `InProcessToolProvider`, `AzureFunctionToolProvider` ([ADR-0003](0003-azure-functions-tool-and-workflow-layer.md)) |
| `ClaimsWorkflowProvider` | `src/core/workflow_provider/protocol.py` | `InProcessClaimsWorkflowProvider`, `DurableClaimsWorkflowProvider` ([ADR-0003](0003-azure-functions-tool-and-workflow-layer.md)) |

Each Protocol defines the exact method signatures its callers need and nothing else — e.g.,
`ConversationRepository` exposes `create_conversation`/`get_conversation`/`list_conversations`/
`append_message`, never a Cosmos SDK type or query string.

### Factory pattern (config-driven selection, one function per provider)

Each provider has a `factory.py` with one function (`get_llm_provider`,
`get_conversation_repository`, `get_knowledge_provider`, `get_secret_provider`,
`get_tool_provider`, `get_claims_workflow_provider`) that reads a `Literal[...]`-typed setting
(e.g., `LLMSettings.llm_provider: Literal["mock", "azure_openai", "ollama"]`,
`src/config/settings.py`) and returns the matching concrete implementation. Every settings class
defaults to the free, zero-Azure-dependency option (`mock`, `in_memory`, `local`, `environment`,
`inprocess`) — local development and the entire test suite never require live Azure connectivity
unless a setting is explicitly overridden.

### Dependency inversion (business logic depends on the Protocol, never the concrete class)

`ClaimsAgent`, `BrokerAgent`, `CommercialIntakeAgent`, `SupervisorOrchestrator`, and every Tool
in `src/services/tools/` receive their dependencies exclusively through constructor parameters
typed as the Protocol (`LLMProvider`, `ToolProvider`, etc.), never by importing
`AzureOpenAIProvider` or `CosmosConversationRepository` directly. `src/supervisor/`, `src/agents/`,
`src/tools/`, and `src/llm/`'s own package boundary never import a concrete provider from another
package — only `apps/api/src/api/dependencies.py` does (its own module docstring states this
explicitly: "This is the composition root... `src/supervisor/`, `src/tools/`, `src/prompts/`, and
`src/llm/` never import any concrete agent, tool, prompt provider, or LLM provider — adding a new
one means adding lines here, not touching any framework.").

### Swappable implementations without touching business logic

Because `get_llm_provider()`, `get_tool_provider()`, etc. are each defined exactly once and
`@lru_cache`d, swapping a backend is a **configuration change**, not a code change:

- `LLM_PROVIDER=mock` (tests, local dev) → `azure_openai` (DEV/staging/prod) — no `ClaimsAgent`,
  `BrokerAgent`, or `CommercialIntakeAgent` code changes; verified by the same agent test suites
  passing unchanged against `MockLLMProvider`.
- `TOOL_PROVIDER=inprocess` → `azure_functions`, `CLAIMS_WORKFLOW_PROVIDER=inprocess` →
  `durable` — `ClaimsAgent`'s constructor parameter (`tool_executor`) accepts any object
  structurally satisfying `ToolProvider`; no Agent code changed when this abstraction was
  introduced ([ADR-0003](0003-azure-functions-tool-and-workflow-layer.md)).
- `KNOWLEDGE_PROVIDER=local` → `azure_ai_search` — `KnowledgeRetriever` (`src/rag/retriever.py`)
  is constructed once with whichever `KnowledgeProvider` the factory returns; `ClaimsAgent`/
  `BrokerAgent`/`CommercialIntakeAgent` depend on `KnowledgeRetriever` alone.
- `SECRET_PROVIDER=environment` → `key_vault` — every provider that needs a credential
  (`AzureOpenAIProvider`, `AzureAISearchProvider`, `AzureFunctionToolProvider`,
  `DurableClaimsWorkflowProvider`) receives an already-resolved `SecretProvider` instance from
  `dependencies.py`; none reads an environment variable directly for a secret value.

## Alternatives considered

- **A single monolithic settings/config object with `if` branches inside each Agent.** Rejected:
  this would put Azure-SDK-specific imports and branching logic directly in Agent code, defeating
  the "agents never know where a dependency lives" requirement that lets tests run with zero Azure
  connectivity, and would need to be repeated in every Agent rather than defined once per
  provider.
- **A general-purpose dependency-injection framework/container.** Rejected: `@lru_cache`-decorated
  factory functions plus Python's own Protocol structural typing already give singleton lifetime
  management and interface-based substitution without adding a new third-party framework
  dependency — consistent with CLAUDE.md §5's instruction not to add libraries/frameworks a PBI
  doesn't require.
- **Concrete-class type hints with runtime `isinstance` branching instead of Protocols.**
  Rejected: `typing.Protocol` gives structural typing (any object with matching methods satisfies
  the interface, as used deliberately for `ToolExecutor` satisfying `ToolProvider` without
  inheritance — see [ADR-0003](0003-azure-functions-tool-and-workflow-layer.md)) with full
  static type-checking support (`mypy`), which concrete-class branching would not provide as
  cleanly.

## Consequences

- Positive: every provider swap to date (`inprocess`→`azure_functions`,
  `inprocess`→`durable`, `mock`→`azure_openai`/`ollama`, `local`→`azure_ai_search`,
  `environment`→`key_vault`, `in_memory`→`cosmos`) has been implemented and tested without a
  single Agent-level code change — direct evidence the pattern delivers on its intent. New
  providers (e.g., a future LLM vendor) follow an established, low-risk recipe: add a Protocol
  implementation, add a factory branch, add a settings literal.
- Positive: the entire test suite runs with zero live Azure dependency by relying on each
  provider's default (mock/in-memory/local/environment/in-process) setting — a direct enabler of
  CLAUDE.md §11's fast, focused validation expectations.
- Negative / accepted trade-off: six parallel Protocol/factory/settings triads add indirection a
  simpler, single-backend design would not need. Accepted because CLAUDE.md's own architecture
  principles (#3 Tool Calling, #4 no direct DB access, #6 security by design via Managed Identity)
  and repeated real provider swaps already exercised in this repository (not hypothetical future
  ones) justify the abstraction — this is the "rule of three" applied to an already-proven need,
  not speculative design.
- `apps/api/src/api/dependencies.py` is a single, growing file with wide import breadth — an
  accepted concentration of composition-root responsibility, consistent with the pattern's own
  intent (one place to look, not scattered wiring).

## Relationship with other ADRs

This ADR documents the general pattern; it does not restate the specific implementation details
already covered elsewhere:

- [ADR-0003](0003-azure-functions-tool-and-workflow-layer.md) — `ToolProvider`/
  `ClaimsWorkflowProvider`, the first providers introduced explicitly to resolve an
  architecture-drift finding.
- [ADR-0004](0004-conversation-store-selection.md) — `ConversationRepository`'s two
  implementations and why Cosmos DB was chosen as the Azure-backed one.
- [ADR-0009](0009-conversation-memory-strategy.md) — how conversation state, itself persisted
  through the `ConversationRepository` this pattern provides, is structured and owned.

## Review triggers

- Before adding a seventh provider family — confirm the same Protocol/factory/settings shape
  still fits, or whether a genuinely different pattern is warranted.
- If `apps/api/src/api/dependencies.py` growth becomes difficult to navigate — consider splitting
  by provider family, without changing the underlying pattern this ADR documents.
- Before introducing any general-purpose DI framework — re-confirm the "alternatives considered"
  reasoning against the codebase's actual size at that time.

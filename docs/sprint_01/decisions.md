# Sprint 01 Decisions and Deviations

Record sprint-specific decisions and deviations. Cross-sprint decisions belong in ADRs.

## 2026-08-07 — PBI-01-01: Docker build context widened to repo root for `apps/api`

**Decision:** `apps/api/src/main.py` now depends on the shared, reusable `src/` package (`src.supervisor`, `src.agents`, `src.domain`, `src.services`) for the first time. The existing Docker build context (`./apps/api`, set in PBI-00-02/00-03) has no visibility outside that directory, so the image would not have contained `src/` at all. Changed `docker-compose.yml`'s `api` service to `context: .` / `dockerfile: apps/api/Dockerfile`; the Dockerfile now copies `apps/api/src` to `/app/app_src` (kept importable as bare `main`/`api`/`config`/`observability` via `--app-dir`) and repo-root `src/` to `/app/src` (importable as `src.*` via `ENV PYTHONPATH=/app`). Replaced `apps/api/.dockerignore` (no longer read, since the build-context root moved) with a new repo-root `.dockerignore`.

**Deviation/status change:** A necessary correction to keep this PBI's own deliverable (`POST /chat`) actually deployable, not a deviation from prior guidance — treated as a prerequisite per explicit user instruction, not scope creep. `apps/web`'s build context and Dockerfile are unaffected.

**How to apply:** Any future top-level `src/` subpackage the API needs will already be visible under `/app/src` in the image — no further Dockerfile changes needed unless a new *runtime* dependency (e.g. `azure-cosmos` if `CONVERSATION_STORE_PROVIDER=cosmos` is ever used in a deployed API container) needs adding to the `pip install` step, which it does not yet (default `in_memory`/`environment` providers need nothing extra).

## 2026-08-07 — PBI-01-01: added a 4th mock agent (`FallbackAgent`) for the `UNKNOWN` intent

**Decision:** The PBI explicitly requested three mock agents (Claims, Broker, Commercial Intake). A `FallbackAgent` was added and registered for `IntentCategory.UNKNOWN` so the `AgentRegistry` has a deterministic entry for every intent the rule-based resolver can produce, keeping `SupervisorOrchestrator.handle()` fully registry-driven — no special-casing "no agent found" for `UNKNOWN` specifically, and no unhandled `AgentNotFoundError` for ordinary unmatched chat input (e.g. "hello").

**Deviation/status change:** A small, deliberate addition beyond the literal 3-agent list, flagged explicitly rather than silently included. Still a deterministic, no-business-logic mock agent, consistent with every constraint the PBI placed on the other three.

**How to apply:** Any future intent category added to `IntentCategory` should have a registered agent (real or fallback) before being wired into the resolver, to preserve the "always resolvable, no branching" registry property this decision established.

## 2026-08-07 — PBI-01-02: branch cut before PBI-01-01 was merged to `main`; resolved via fast-forward merge

**Decision:** `feat/pbi-01-02-tool-framework` was created from `main` before `feat/pbi-01-01-supervisor-agent` (already committed) had been merged. At the start of PBI-01-02, `src/supervisor/`, `src/agents/`, `apps/api/src/api/dependencies.py`, `chat.py`, and the Docker build-context fix were all absent from the branch despite PBI-01-01 being marked complete in `docs/sprint_01/README.md`. Verified via `git merge-base HEAD feat/pbi-01-01-supervisor-agent` that the current branch tip *was* the merge-base (i.e., a pure fast-forward, zero divergence, zero conflict risk), then ran `git merge feat/pbi-01-01-supervisor-agent --ff-only`, which succeeded cleanly (32 files, no conflicts) before any PBI-01-02 code was written.

**Deviation/status change:** Not a code deviation — a repository/branch-topology issue, the same class already documented for PBI-00-01/00-02 in `docs/sprint_00/decisions.md`. Nothing was lost, discarded, or reverted; this was purely a not-yet-merged-branch situation caught and fixed before work began.

**How to apply:** Before starting a PBI whose scope explicitly builds on a previous PBI's files (as PBI-01-02's instructions explicitly did, listing `src/supervisor`, `src/agents`, `apps/api/src/api/dependencies.py` as inspection targets), verify those files actually exist on the current branch first — do not assume a prior PBI being "complete" in sprint docs means its commit is reachable from the branch in hand.

## 2026-08-07 — PBI-01-02: `ToolResult` generic kept as `Generic[T]`, not PEP 695 syntax

**Decision:** `ruff` (configured `target-version = "py312"`) flagged `class ToolResult(BaseModel, Generic[ToolOutputT]):` with `UP046`, recommending Python 3.12's newer `class ToolResult[ToolOutputT](BaseModel):` syntax. That syntax is a `SyntaxError` on Python 3.11, the only interpreter available to actually import/run/test this code in this environment (pre-existing R-01 gap, documented since Sprint 00). Kept the portable `Generic[T]` form — fully correct and supported on 3.12 too — and suppressed the rule locally with `# noqa: UP046` plus an inline comment explaining why.

**Deviation/status change:** A pragmatic, explicitly-justified rule suppression, not a quality-gate weakening — `ruff check` is still clean overall, and the suppression is scoped to the one line it applies to, not a blanket repo-wide ignore.

**How to apply:** Revisit this suppression once the local/CI Python interpreter gap (R-01) is actually closed (Python 3.12 installed) — at that point PEP 695 syntax becomes safe to adopt and the `noqa` can be removed. Any other generic class added before then should follow the same `Generic[T]` + justified `noqa` pattern for consistency.

## 2026-08-07 — PBI-01-03: prompts stored as Markdown with YAML frontmatter, in CLAUDE.md's existing `configs/prompts/` folders

**Decision:** Each prompt is one Markdown file with a YAML frontmatter block (`version`, `purpose`, `allowed_tools`, `prohibited_decisions`, `change_notes`, `required_variables`) followed by the template body. Files live under the `configs/prompts/{supervisor,claims,broker_services,commercial_intake}/` folders CLAUDE.md §6 and PBI-00-01 already reserved (previously empty placeholders), plus one new `fallback/` folder. Logical identifiers (e.g. `broker.system`) map to these folder names via an explicit table in `FileSystemPromptProvider`, not a 1:1 rename — `broker` → `broker_services`, `commercial` → `commercial_intake` — proving the "Agents never know storage paths" abstraction is real.

**Deviation/status change:** None — Markdown is what the PBI's own instructions preferred, and frontmatter is the standard, minimal-dependency way to carry typed metadata inside a single readable file without inventing a second sidecar-file convention.

**How to apply:** Any new prompt (future agent, future intent) should follow this same one-file, frontmatter + body pattern and be added to `_NAMESPACE_TO_DIRECTORY` in `filesystem_provider.py` if its namespace doesn't already map to an existing folder.

## 2026-08-07 — PBI-01-03: `PromptManager` raises typed exceptions rather than returning a Result object

**Decision:** Unlike `ToolExecutor` (PBI-01-02), which always returns a `ToolResult` and never raises — because it must survive arbitrary, unpredictable Tool implementations — `PromptManager.render()`/`get_metadata()` raise `PromptNotFoundError`/`PromptValidationError`/`PromptRenderError` directly to the caller. Prompts are a simpler, fully first-party-controlled component; letting callers `except` a specific typed exception (or let it propagate) is more idiomatic here and avoids adding an unnecessary `success`/`error` wrapper type for a component with no external/unpredictable execution step.

**Deviation/status change:** A deliberate architectural difference from the Tool framework's pattern, not an inconsistency — both frameworks still "normalize typed failures" as required, just via different, each contextually appropriate, mechanisms (`ToolExecutor`: always-succeeds-with-a-result; `PromptManager`: typed-exceptions). `PromptManager._load()` still normalizes any *unexpected* (non-Prompt-typed) provider exception into `PromptValidationError`, so no raw, provider-specific exception ever escapes the framework boundary either way.

**How to apply:** Any Agent calling `PromptManager` should be prepared to catch `PromptNotFoundError`/`PromptValidationError`/`PromptRenderError` if it wants to degrade gracefully (the same way `ClaimsAgent` already does for `ToolExecutor` failures via the `ToolResult.success` flag) — a future PBI adding that graceful-degradation behavior to `ClaimsAgent` for prompt failures specifically was considered but not implemented here, to keep this PBI's Agent change minimal and focused on proving the wiring.

## 2026-08-07 — PBI-01-04: `openai` SDK (`AsyncAzureOpenAI`) chosen for `AzureOpenAIProvider`, with Entra ID as the default auth path

**Decision:** `AzureOpenAIProvider` uses the official `openai` Python package's `AsyncAzureOpenAI` client (not `azure-ai-inference` or a hand-rolled REST client), since it has first-class, well-documented Azure support and a native `azure_ad_token_provider` parameter for Entra ID authentication — satisfying "prefer Microsoft Entra ID / DefaultAzureCredential-compatible authentication when technically supported by the chosen SDK" directly rather than needing a workaround. By default (`azure_openai_use_api_key=False`), the provider constructs `DefaultAzureCredential()` + `get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")` and never touches an API key at all. Only when `azure_openai_use_api_key=True` does it fetch a key, and only through the existing `SecretProvider` abstraction (reusing the `azure-openai-api-key` secret name already reserved in PBI-00-06's decisions.md), never `os.environ` directly.

**Deviation/status change:** None — this is the literal, most standard implementation of the PBI's own stated preference. Added `openai` to a new optional `azureopenai` pyproject extra (not installed by default), matching the `cosmos`/`keyvault` extras' lazy-import pattern established in PBI-00-05/00-06.

**How to apply:** Any future provider needing Azure AI service credentials should follow the same shape: Entra ID by default via the SDK's own native support, API-key/secret access routed only through `SecretProvider`, and the SDK itself added as a new optional extra rather than a core dependency.

## 2026-08-07 — PBI-01-04: fixed an outdated test assumption in `test_mock_agents.py`

**Decision:** `test_agent_response_is_identical_regardless_of_input_message` asserted `ClaimsAgent`'s full response text was invariant to the input message — true before this PBI (the response was a fixed template plus a fixed-claim-number tool lookup), but no longer true, correctly, once the agent calls `LLMProvider` with the actual user message (`MockLLMProvider`'s output varies with the last user message's length by design). Rewrote the test to check what remains genuinely invariant (agent name, intent, the prompt identifier/version annotation) instead of full-string equality; per-input determinism is now covered by the new `tests/unit/agents/test_claims_agent_llm_integration.py`.

**Deviation/status change:** A correct fix to an assumption invalidated by this PBI's own intended behavior change, not a regression or a quality-gate weakening — the replacement test is at least as strict, just checking the right invariant.

**How to apply:** Any future PBI that makes an Agent's response genuinely depend on more of its input (as intended, since that's the whole point of wiring in an LLM) should expect — and correct, not suppress — any prior test that assumed full-response determinism-regardless-of-input for that Agent.

## 2026-08-07 — PBI-01-05: claims-intake working state stored in `Conversation.metadata`, not a new store

**Decision:** `ClaimsIntakeState` (which required fields are still missing, policy validation results, claim reference, adjuster) is serialized to JSON and round-tripped through `Conversation.metadata["claimsIntakeState"]` / `ConversationContext.metadata` / `AgentResponse.metadata` — new, additive plumbing through `src/supervisor/models.py`, `context.py`, `orchestrator.py`, and a new optional `metadata` parameter on `ConversationRepository.append_message()` (implemented in both `InMemoryConversationRepository` and `CosmosConversationRepository`). CLAUDE.md §4.3 states "Core business truth (policies, claims, payments, commissions) must never be modeled or stored here — only conversational state." This is judged to be conversational state, not core business truth: it is in-progress session notes needed to resume a multi-turn intake, not the authoritative claim record — the authoritative record is whatever a real claims system would hold, only simulated here via `ClaimRegistrationTool`'s synthetic reference generation.

**Deviation/status change:** An additive, backward-compatible extension (all new fields/parameters are optional with safe defaults) — no existing `ConversationRepository` caller or test needed to change its call shape.

**How to apply:** Any future Agent needing multi-turn working state should follow the same pattern (typed state model, serialized into `metadata`, deserialized defensively — a corrupt/incompatible stored snapshot must never crash the conversation, see `ClaimsAgent._load_state()`) rather than introducing a new store or modeling business facts directly on `Conversation`.

## 2026-08-07 — PBI-01-05: only "policy not found" blocks claim registration; inactive policy / payment issues are surfaced, not gated

**Decision:** The claims-intake state machine (`src/agents/claims/workflow.py`) treats an inactive policy and an outstanding payment issue as facts to report, never as a reason to stop registration. Only a policy number that cannot be found at all blocks progression (the caller is asked to double-check and re-supply it). This is the only design that satisfies both explicit PBI-01-05 requirements simultaneously: "validate a synthetic policy... determine whether it is active... determine whether payments are current" (implies these facts must be gathered and reported) and "must not determine final coverage, reject claims, or authorize indemnity" (implies the Agent cannot use those facts to block or approve anything).

**Deviation/status change:** None — a direct, necessary reading of the PBI's own stated boundary, not a deviation.

**How to apply:** Any future Agent capability that reports a business-status fact (active/inactive, current/overdue, valid/invalid) must default to *reporting*, not *gating*, unless the PBI or an ADR explicitly authorizes that Agent to make the resulting decision.

## 2026-08-07 — PBI-01-05: `ClaimsAgent`'s user-facing text is always deterministic; the LLM is invoked but never the source of business wording

**Decision:** `MockLLMProvider`'s output is derived only from message length/count (never meaning), so it cannot perform real NLU or produce meaningful, on-topic phrasing for a "concise, professional" claims conversation. `ClaimsAgent`'s response text is therefore built entirely from the deterministic state-machine notices; `PromptManager.render()` and `LLMProvider.generate()` are still called every turn (so both frameworks stay genuinely wired and the same code works unmodified against `AzureOpenAIProvider`), but their result is only ever appended as a provable annotation (`[prompt=claims.system@2.0.0] [llm=mock-llm]`), never blended into the business content. This intentionally changes the response format `PBI-01-03`/`PBI-01-04` established (which embedded the LLM's raw text) — the 4 pre-existing Claims Agent dependency-injection test files were updated accordingly, the same class of change already documented in the PBI-01-04 entry above.

**Deviation/status change:** A deliberate, PBI-01-05-scoped evolution of the response format, not a regression — CLAUDE.md §3 ("the LLM is not the source of truth") required it once the Agent had real business facts to protect.

**How to apply:** Any future Agent with real business logic should follow the same shape: deterministic facts drive the user-facing text; LLM/Prompt invocation stays provable (e.g. via an annotation or structured metadata) without ever letting LLM-generated wording become a business fact.

## 2026-08-07 — PBI-01-05: fixed a real Supervisor routing bug — ambiguous follow-ups now stay with the conversation's current agent

**Decision:** `SupervisorOrchestrator.handle()` re-resolves intent from every individual message via `RuleBasedIntentResolver`'s keyword matching. A bare follow-up mid claims-intake (a policy number, a date, "yes"/"no") contains no CLAIMS keywords, so before this fix it resolved to `UNKNOWN` and was routed to `FallbackAgent`, breaking the conversation — discovered via the new `POST /chat` end-to-end test (`tests/unit/api/test_chat.py::test_chat_drives_a_full_claim_report_end_to_end_through_the_real_api`), not by unit-level Agent tests, which call `ClaimsAgent.handle()` directly and never exercise Supervisor routing at all. Fixed by adding `current_agent: str | None` to `ConversationContext` (populated in `context.py` from the existing `Conversation.current_agent` field, which was already stored but never read back) and a new `SupervisorOrchestrator._resolve_agent()` method: when intent resolves to `UNKNOWN` and the conversation already has a `current_agent`, the Supervisor looks that same Agent instance up via `AgentRegistry.list()` (an existing capability) instead of falling through to `FallbackAgent`. A message that clearly matches a *different* intent still switches agents normally.

**Deviation/status change:** A necessary bug fix surfaced by this PBI's own required end-to-end test coverage, not scope creep — without it, PBI-01-05's own explicit success criterion ("gathers missing info over multiple turns... via `POST /chat`") does not hold. This is a single, uniform, agent-agnostic fallback rule (applies identically regardless of which Agent is current), not per-agent-type branching, so it does not compromise `orchestrator.py`'s "no if/else selects the agent" property in spirit — it is a continuity rule that runs *before* the registry lookup, not a replacement for it.

**How to apply:** Any future Agent with a multi-turn flow whose follow-up messages may lack intent keywords benefits from this fallback automatically, with no per-agent code. If a future PBI needs finer-grained control (e.g. an explicit "cancel"/"start over" keyword that should always re-resolve intent even mid-flow), extend `_resolve_agent()`'s single condition, not add a second one — keep this a one-rule fallback.

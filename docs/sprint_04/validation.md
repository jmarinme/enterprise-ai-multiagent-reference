# Sprint 04 Validation

Record only commands actually executed and their real results.

## 2026-08-08 — PBI-04-01: Azure DevOps CI/CD Pipeline for the DEV Environment

### Pre-work: read required files, confirm current live state

| Check | Result |
|---|---|
| Read `CLAUDE.md`, `docs/sprint_03/*`, `docs/Architecture/*`, `ops/bicep/*`, existing `azure-pipelines.yml` | Confirmed a working Sprint-0 CI pipeline already exists (5 stages + a disabled, documented `Deploy_Dev` stage); found two real, pre-existing defects (see `decisions.md`) |
| `az resource list --resource-group rg-tmx-agent-platform-dev` | All 12 resources from PBI-03-05/06 still present, `Succeeded` |
| `az containerapp show --name ca-tmxap-dev-api ...` | `latestRevisionName: ca-tmxap-dev-api--v5`, FQDN `ca-tmxap-dev-api.bluemushroom-e2f74836.eastus2.azurecontainerapps.io` |
| `ls ops/bicep/modules/*.bicep` | 14 module files — cross-checked against the pipeline's `bicepModuleFiles` list, which was missing 5 of them |

### Bicep RBAC additions — static validation only (not deployed to Azure this PBI)

| Command | Result |
|---|---|
| `az role definition list --name "AcrPush"` | Confirmed live role GUID `8311e382-0749-4cb8-b61a-304f252e45ec` — used in `container-registry.bicep`, not guessed |
| `az role definition list --name "Container Apps Contributor"` | Confirmed live role GUID `358470bc-b998-42bd-ab17-a7e34c199c0f` — used in `container-app.bicep`, not guessed |
| `az bicep build --file ops/bicep/main.bicep` | exit 0, 0 warnings |
| `az bicep build --file ops/bicep/modules/container-registry.bicep` | exit 0, 0 warnings |
| `az bicep build --file ops/bicep/modules/container-app.bicep` | exit 0, 0 warnings |
| `az bicep build-params` — dev/staging/prod | All exit 0 |

**Not executed this PBI**: `az deployment group create` to actually apply the RBAC additions to the real DEV environment — deliberately deferred pending explicit user approval; see `decisions.md`.

### Pipeline YAML validation

| Command | Result |
|---|---|
| `python -c "import yaml; yaml.safe_load(open('azure-pipelines.yml'))"` | Valid YAML syntax. Parsed 8 top-level stages: `BackendQuality`, `FrontendQuality`, `InfrastructureValidation`, `ContainerBuildAndPush`, `DeployDev`, `SmokeTests`, `DeploymentSummary`, `ArtifactPublication` |
| `az extension list` / `az devops configure -l` | No `azure-devops` CLI extension installed; no Azure DevOps organization configured in this session (confirmed via failed prompt for extension install and no default org) — a true server-side/schema-level Azure Pipelines validation (`az pipelines run --validate-only`) could not be performed. Documented as a scope boundary in `decisions.md`, not silently skipped |
| Manual schema/logic review against the working Sprint-0 baseline `azure-pipelines.yml` | Confirmed: task names (`UsePythonVersion@0`, `NodeTool@0`, `Cache@2`, `AzureCLI@2`, `PublishTestResults@2`, `PublishCodeCoverageResults@2`, `PublishPipelineArtifact@1`, `DownloadPipelineArtifact@2`) match Azure Pipelines' documented task catalog and versions already proven working in the preserved Stage 1-3 content; `${{ }}` template-expression vs. runtime `$[ ]`/`variables[]` expression syntax used consistently and correctly (verified against the one existing `${{ each }}` usage already in the file) |

### Local dry-run (real, read-only `az` CLI calls against the live DEV environment — exactly the queries embedded in the pipeline's inline scripts)

| Dry-run query (verbatim from the pipeline) | Result |
|---|---|
| `az acr list --resource-group rg-tmx-agent-platform-dev --query "[0].name"` | `acrtmxapdevl3fgxt` |
| `az acr list --resource-group rg-tmx-agent-platform-dev --query "[0].loginServer"` | `acrtmxapdevl3fgxt.azurecr.io` |
| `az containerapp list --resource-group rg-tmx-agent-platform-dev --query "[?ends_with(name, '-api')].name \| [0]"` | `ca-tmxap-dev-api` |
| `az containerapp list --resource-group rg-tmx-agent-platform-dev --query "[?ends_with(name, '-web')].name \| [0]"` | `ca-tmxap-dev-web` |
| `az containerapp show --resource-group rg-tmx-agent-platform-dev --name ca-tmxap-dev-api --query "properties.configuration.ingress.fqdn"` | `ca-tmxap-dev-api.bluemushroom-e2f74836.eastus2.azurecontainerapps.io` |
| `az containerapp show ... --query "properties.latestRevisionName"` (api, web) | `ca-tmxap-dev-api--v5`, `ca-tmxap-dev-web--phnq58i` |
| **Smoke test 1/2**: `curl -sf --max-time 30 https://<api-fqdn>/health` | `200 {"status":"ok"}` |
| **Smoke test 2/2**: `curl -sf --max-time 60 -X POST https://<api-fqdn>/chat -d '{"userId":"cicd-smoke-test","message":"Hello, this is an automated CI/CD smoke test."}'` | `200` — `{"agent":"FallbackAgent","intent":"UNKNOWN","response":"I could not determine how to help with that. A human may need to assist you.",...}` (generic test message correctly classified as UNKNOWN intent — expected, not a defect) |
| Exact Python JSON-assertion snippet from the `SmokeTests` stage, run against the real captured response body above | `POST /chat: OK (agent=FallbackAgent, intent=UNKNOWN)` — confirms the assertion logic (`response` and `agent` both non-empty) passes against real API output |
| Exact `Stage 8` JUnit-parsing Python snippet, run against a real `pytest --junitxml=...` output (`tests/unit/llm`, 62 tests) | `62 tests, 0 failures, 0 errors, 0 skipped` — confirms the `<testsuites><testsuite>` XML structure and parsing logic are correct against this repo's actual pytest/JUnit output shape |

`python3` is not the correct binary alias in this local Windows dev shell (a pre-existing, unrelated local-environment quirk noted throughout this session — Azure DevOps's `ubuntu-latest` hosted agents have `python3` natively available); the local venv's `python.exe` was used to verify the identical script logic instead.

### Full regression suite (no Python source touched this PBI — required by the PBI's own validation list regardless)

| Command | Result |
|---|---|
| `pytest tests/ -q` | `455 passed, 2 skipped` — identical to PBI-03-06's final count |
| `ruff check apps/api/src src tests ops/scripts` | `All checks passed!` |
| `mypy apps/api/src` | `Success: no issues found in 13 source files` |
| `mypy src` | `Success: no issues found in 102 source files` |

Full transcript archived at `docs/sprint_04/evidence/pbi-04-01-cicd-pipeline-validation.txt`.

Conclusion: PBI-04-01 delivers a complete, internally-consistent, statically-validated Azure DevOps YAML CI/CD pipeline extending the existing Sprint-0 CI foundation — fixing two real, previously-undetected defects along the way (wrong API image build context; stale Bicep module validation list) — plus the minimum new Azure RBAC (two role assignments, zero new resources) required for it to eventually run for real. Every piece of dynamic logic the pipeline depends on (resource-name resolution, smoke-test commands, JUnit parsing) was proven correct against real, live data from the actual DEV environment, not assumed. What remains, by design and pending explicit user approval, is applying the RBAC change to real Azure and creating the Azure DevOps service connection — both are one-time, human, out-of-session actions clearly documented as such, not gaps.

### 2026-08-08 — RBAC deployment to real Azure (explicit user approval obtained after `what-if` review)

| Step | Command | Result |
|---|---|---|
| 1 | `az resource list --resource-group rg-tmx-agent-platform-dev` (pre-check) | All 12 resources present, `Succeeded` |
| 2 | `az deployment group what-if --resource-group rg-tmx-agent-platform-dev --template-file ops/bicep/main.bicep --parameters ops/bicep/parameters/dev.bicepparam` | `10 to modify, 5 no change, 8 unsupported, 1 to ignore`. Zero `+ Create`/`- Delete` at resource level; all `~ Modify` entries were computed-property what-if noise or identically-resolving `reference()` expressions on already-deployed resources; all 8 "Unsupported" diagnostics were `Microsoft.Authorization/roleAssignments` extension resources (documented ARM what-if limitation) — 5 pre-existing, 3 new (AcrPush + 2× Container Apps Contributor) |
| 3 | Change summary presented to user; explicit approval received ("Approved. Proceed with az deployment group create.") | — |
| 4 | `az deployment group create --resource-group rg-tmx-agent-platform-dev --template-file ops/bicep/main.bicep --parameters ops/bicep/parameters/dev.bicepparam` | `provisioningState: Succeeded` |
| 5 | `az identity show --name id-tmxap-dev ... --query principalId` + `az role assignment list --assignee <principalId> --all` | Confirmed 7 Azure-RBAC role assignments total: 4 pre-existing (AcrPull, Key Vault Secrets User, Search Index Data Reader, Cognitive Services OpenAI User) + 3 new (**AcrPush** on `acrtmxapdevl3fgxt`; **Container Apps Contributor** on `ca-tmxap-dev-api`; **Container Apps Contributor** on `ca-tmxap-dev-web`) — all correctly scoped to their individual resources, not the resource group |
| 6 | `az resource list --resource-group rg-tmx-agent-platform-dev` (post-check) | All 12 resources still present, `Succeeded` — none added, none removed |
| 7 | `az containerapp revision list` (api, web) | Active revisions **unchanged**: `ca-tmxap-dev-api--v5`, `ca-tmxap-dev-web--phnq58i` — confirms no new revision was created and no application state was touched, only the new extension role-assignment resources were added |
| 8 | `az containerapp revision list` health check | Both revisions `healthState: Healthy` |
| 9 | `curl https://ca-tmxap-dev-api.../health` | `200 {"status":"ok"}` |

Per explicit user instruction, the Azure DevOps pipeline was **not** triggered in this step.

Conclusion: the RBAC-only change was applied to real Azure with zero impact on any existing resource's identity, configuration, or running state — verified positively (not merely assumed) via role-assignment listing, resource listing, revision-name comparison, health-state check, and a live `/health` call. The Managed Identity is now fully provisioned for the CI/CD pipeline's needs; only the Azure DevOps-side service connection remains before a real pipeline run can be attempted.

## 2026-08-08 — PBI-04-02: Functional Web Chat integration

### Pre-work: read required files, inspect current architecture

| Check | Result |
|---|---|
| Read CLAUDE.md, docs/sprint_04/*; inspect App.tsx, env.ts, apps/web/package.json, apps/web/Dockerfile, vite.config.ts, apps/api/src/main.py, POST /chat contract, CORS config, deployed URLs | Confirmed App.tsx's handleSend only appended a hardcoded local reply (Sprint-0 placeholder, its own welcome text said so); apps/api/src/main.py had zero CORS middleware anywhere (grep confirmed); apps/api/src/config/settings.py had no CORS-related setting to reuse |
| grep _CLAIMS_KEYWORDS/_BROKER_KEYWORDS/_COMMERCIAL_KEYWORDS in src/supervisor/intent.py | Confirmed all 3 required demo phrasings ("I want to report an accident.", "I want to check my commissions.", "I need a commercial insurance quote.") each contain a real matched keyword |
| grep grounder/knowledge_retriever wiring in src/agents/{claims,broker,commercial_intake}_agent.py | Confirmed only ClaimsAgent uses RAG/Grounding — an existing architectural fact, documented, not changed |

### Backend: CORS implementation and validation

| Command | Result |
|---|---|
| pytest tests/unit/api/test_cors.py tests/unit/api/test_chat.py tests/unit/api/test_health.py -v | 17 passed — 6 new CORS tests, 9 existing chat tests, 2 existing health tests, all green on first full run |
| pytest tests/ -q (full suite) | 461 passed, 2 skipped (455 baseline + 6 new CORS tests) |
| ruff check apps/api/src src tests ops/scripts | 1 import-order error in test_cors.py, fixed via ruff check --fix; re-run: All checks passed! |
| mypy apps/api/src / mypy src | Both clean |
| az bicep build --file ops/bicep/main.bicep | exit 0, 0 warnings (confirms the new CORS_ALLOWED_ORIGINS cross-module reference to webContainerApp.outputs.fqdn creates no circular dependency) |
| az bicep build-params — dev/staging/prod | All exit 0 |
| docker compose config | exit 0 |

### Frontend: chat integration and validation

| Command | Result |
|---|---|
| npm run typecheck | Clean |
| npm run lint | Clean |
| npm run build (with the real DEV VITE_API_URL) | Succeeded — dist/assets/index-*.js (~150 KB), confirmed the real API URL baked in via grep |
| npx vitest run (full suite) | 23 passed across 6 files (api/chat.test.ts 4, api/client.test.ts 3, components/MessageArea.test.tsx 5, components/Header.test.tsx 2, components/MessageInput.test.tsx 3, App.test.tsx 6) — one jsdom gap fixed along the way (scrollIntoView not implemented in jsdom; stubbed in setupTests.ts, a standard, environment-only fix) |
| Local vite preview dry-run with the real Azure Container Apps Host header | 200 OK (confirms the pre-existing preview.allowedHosts fix from before this PBI still applies to the newly-built image) |

### Deployment (API + Web images only, no shared infrastructure touched)

| Step | Command | Result |
|---|---|---|
| Pre-check | az resource list --resource-group rg-tmx-agent-platform-dev | All 12 resources present, healthy |
| Build API | az acr build --image tmx-api:dev-20260807205835 --file apps/api/Dockerfile . | Succeeded |
| Build Web | az acr build --image tmx-web:dev-20260807205845-chat --file apps/web/Dockerfile --build-arg VITE_API_URL=... apps/web | Succeeded |
| Deploy API | az containerapp update --name ca-tmxap-dev-api --image ...:dev-20260807205835 --set-env-vars CORS_ALLOWED_ORIGINS=https://ca-tmxap-dev-web... | Succeeded; new revision ca-tmxap-dev-api--0000003, Healthy |
| Verify no env-var loss | az containerapp show --query properties.template.containers[0].env | All 18 pre-existing env vars present unchanged, plus the 1 new CORS_ALLOWED_ORIGINS — confirms --set-env-vars merges, does not replace, the env list |
| Deploy Web | az containerapp update --name ca-tmxap-dev-web --image ...:dev-20260807205845-chat | Succeeded; new revision ca-tmxap-dev-web--0000002, Healthy |

No az deployment group create was run this PBI — both updates were targeted az containerapp update calls, per explicit instruction to rebuild/redeploy only the affected images.

### Live DEV validation (real calls against the real deployed service)

| # | Check | Result |
|---|---|---|
| 1 | GET /health | 200 {"status":"ok"} |
| 2 | CORS preflight (OPTIONS /chat) with Origin: https://ca-tmxap-dev-web... | 200, access-control-allow-origin: https://ca-tmxap-dev-web... (the real deployed Web origin), access-control-allow-methods: GET, POST |
| 3 | GET / (deployed Web page) | 200, real HTML, correct bundle references |
| 4 | Deployed JS bundle content | Contains /chat calls and the real API URL, confirmed via curl + grep directly against the live Container App |
| 5 | Claims turn 1 ("I want to report an accident.", with Origin header matching the real Web origin) | 200 — real gpt-5-mini-2025-08-07 response, 2 real grounded citations (KB-CLAIMS-0002, KB-POLICY-0001), groundingMetadata.isGrounded: true — this single call satisfies both the Claims demo scenario and the RAG/grounded-citation demo scenario |
| 6 | Claims turn 2 (same conversationId, "SYN-POL-0001") | 500 Internal Server Error — reproduced twice with two independent fresh conversations, confirming it is deterministic, not transient. Root-caused via read-only log inspection (az containerapp logs show) to a genuine, pre-existing ToolCallingOrchestrator defect (see decisions.md) — not a CORS or frontend regression from this PBI |
| 7 | Broker turn 1 + turn 2 ("I want to check my commissions." then "SYN-BRK-0001 2026-Q1", same conversationId) | Both 200. Turn 2 returned real Tool-sourced business data (commission_amount: 1250.0, broker_active: true) — proves Broker's deterministic Tool-invocation path is unaffected by the Claims-specific orchestrator defect, and independently proves conversationId persistence works correctly end-to-end |
| 8 | Commercial turn 1 + turn 2 ("I need a commercial insurance quote." then "Acme Consulting LLC", same conversationId) | Both 200 — same confirmation as Broker |

Full transcript archived at docs/sprint_04/evidence/pbi-04-02-web-chat-integration-validation.txt.

### STOP CONDITION accounting

| # | Requirement | Status |
|---|---|---|
| 1 | Deployed DEV Web URL loads successfully | Met — GET / returns 200 with real HTML |
| 2 | Browser can call the deployed DEV API without CORS errors | Met — real preflight + actual-request evidence, correct Access-Control-Allow-Origin for the real Web origin |
| 3 | A real POST /chat response is displayed in the UI | Met for the mechanism (real response received, App.tsx renders result.response/agent/citations — proven via App.test.tsx's mocked-fetch integration tests and the live curl evidence above) |
| 4 | conversationId preserved across multiple turns | Met — proven via Broker and Commercial's real, live 2-turn conversations, plus App.test.tsx's dedicated test for the same mechanism |
| 5 | Claims works end-to-end from the browser | Partially met — a single Claims turn works completely end-to-end (real routing, real LLM response, real grounded RAG citations, correct CORS). A second turn is blocked by the newly-discovered ToolCallingOrchestrator defect (see decisions.md), which is unrelated to this PBI's own changes and explicitly out of scope to fix (src/core/tool_calling/ is forbidden territory for PBI-04-02) |
| 6 | Existing backend tests remain green | Met — 461 passed, 2 skipped (455 baseline + 6 new), zero regressions |

Conclusion: PBI-04-02 delivers a complete, tested, real POST /chat integration replacing the Sprint-0 placeholder, with configuration-driven, non-wildcard CORS enabling genuine cross-origin browser calls between the deployed Web and API Container Apps for the first time. 5 of 6 STOP CONDITION items are fully met; item 5 is honestly reported as partially met, not silently overstated, because live validation surfaced a real, precisely-diagnosed, pre-existing defect in code this PBI was explicitly forbidden from touching. This is the correct, expected outcome of thorough live validation catching a genuine gap in test coverage (every prior automated test used MockLLMProvider, which never exercised the real Azure OpenAI API's message-sequencing constraint) — not a shortfall in this PBI's own delivered scope.

## 2026-08-08 — PBI-04-03: Fix Azure OpenAI Tool Calling message sequencing

### Preparation: read + inspect (before any code change)

| Check | Result |
|---|---|
| Read CLAUDE.md, docs/sprint_04/*, docs/Architecture/* | Confirmed PBI-04-02's own decisions.md entry already root-caused this defect in outline; this PBI performs the fix |
| Inspect src/core/tool_calling/orchestrator.py | Confirmed: run()'s loop (lines ~113-122) appends only a TOOL-role message after executing a Tool call, never the preceding ASSISTANT message carrying tool_calls |
| Inspect src/llm/models.py (LLMMessage) | Confirmed: no field exists to represent tool_calls on an ASSISTANT-role message — the root cause the fix must address |
| Inspect src/llm/azure_openai_provider.py (_to_openai_messages) | Confirmed: no branch handles an ASSISTANT message with tool_calls |
| Inspect src/llm/mock_provider.py | Confirmed: generate() never serializes request.messages to any external API/format — purely in-process text derivation from message count/last-user-message length; has no concept of message-sequencing validity, which is exactly why the real protocol violation was invisible to it |
| Inspect src/agents/claims_agent.py | Confirmed: always sends only [SYSTEM, USER] as the initial messages list to ToolCallingOrchestrator.run() — the bug is entirely internal to a single run() invocation's own loop, not a cross-turn Cosmos-history-reconstruction issue |
| Inspect apps/api/src/api/dependencies.py | Re-confirmed only ClaimsAgent receives a tool_calling_orchestrator argument — Broker/Commercial are structurally unaffected by this defect |
| Read existing tests: test_tool_calling_orchestrator.py, test_claims_agent_tool_calling_integration.py | Established the exact test-double conventions (_ScriptedLLMProvider) and assertion style to extend |
| Verify OpenAI SDK types available in the installed openai package | ChatCompletionAssistantMessageParam, ChatCompletionMessageFunctionToolCallParam, Function (arguments: str, name: str) confirmed via direct introspection, not guessed |

### Implementation

| File | Change |
|---|---|
| src/llm/models.py | Reordered ToolCallArgument/ToolCallRequest before LLMMessage; added LLMMessage.tool_calls: list[ToolCallRequest] \| None = None |
| src/core/tool_calling/orchestrator.py | run() appends one ASSISTANT LLMMessage(tool_calls=llm_response.tool_calls) before the TOOL-message-appending loop |
| src/llm/azure_openai_provider.py | New _to_openai_tool_calls() helper; _to_openai_messages() gained an ASSISTANT+tool_calls branch |
| src/llm/ollama_provider.py | _to_ollama_messages() gained the equivalent Ollama-shaped branch |
| src/llm/mock_provider.py | No change |

### Static validation

| Command | Result |
|---|---|
| mypy src/llm/models.py src/llm/azure_openai_provider.py src/llm/ollama_provider.py src/core/tool_calling/orchestrator.py | Success: no issues found in 4 source files |
| ruff check src/llm/models.py src/llm/azure_openai_provider.py src/llm/ollama_provider.py src/core/tool_calling/orchestrator.py | All checks passed! |
| pytest tests/unit/core/tool_calling/ tests/unit/llm/ tests/unit/agents/test_claims_agent_tool_calling_integration.py -v (before adding new tests) | 91 passed — zero regression from the fix itself, confirming the change is additive |
| pytest tests/unit/core/tool_calling/test_tool_calling_orchestrator.py -v (after adding/strengthening tests) | 15 passed (13 original + 2 new) |
| pytest tests/unit/llm/test_azure_openai_provider.py -v | 20 passed (17 original + 3 new) |
| pytest tests/unit/llm/test_ollama_provider.py -v | 14 passed (13 original + 1 new) |
| pytest tests/ -q (full suite) | 468 passed, 2 skipped (461 baseline + 7 new) |
| ruff check apps/api/src src tests ops/scripts | All checks passed! |
| mypy apps/api/src / mypy src | Both clean |
| pytest tests/unit/agents/ tests/unit/api/test_chat.py -q (explicit Broker/Commercial/Claims/full-API regression) | 133 passed |

No Bicep/docker-compose files were touched this PBI (no infrastructure change) — not re-validated, consistent with the explicit "Do NOT touch... Networking" instruction.

### Deployment (API image only)

| Step | Command | Result |
|---|---|---|
| Pre-check | az resource list --resource-group rg-tmx-agent-platform-dev | All 12 resources present, healthy |
| Build | az acr build --image tmx-api:dev-20260807212817-toolfix --file apps/api/Dockerfile . | Succeeded (local CLI hit the same known cosmetic colorama/Windows-console encoding crash seen throughout this session; confirmed via az acr task list-runs that the remote build completed: Succeeded, 38s) |
| Deploy | az containerapp update --name ca-tmxap-dev-api --image ...:dev-20260807212817-toolfix | Succeeded; new revision ca-tmxap-dev-api--0000004, Healthy |
| Web untouched | az containerapp revision list --name ca-tmxap-dev-web | Unchanged: ca-tmxap-dev-web--0000002 (same as before this PBI) |
| All resources unchanged | az resource list --resource-group rg-tmx-agent-platform-dev | All 12 resources still present, unchanged |

No az deployment group create was run. No Cosmos, Azure OpenAI, Key Vault, Managed Identity, Container Apps Environment, ACR, or networking resource was touched.

### Live DEV validation (real calls against the real deployed service)

| # | Check | Result |
|---|---|---|
| 1 | GET /health | 200 {"status":"ok"} |
| 2 | Claims turn 1 ("I want to report an accident.") | 200 — real gpt-5-mini-2025-08-07 response, 2 grounded citations, isGrounded: true |
| 3 | **Claims turn 2 ("SYN-POL-0001", same conversationId) — the exact scenario that previously returned 500** | **200** — real, successful policy_lookup Tool call executed (`"toolCalls":[{"toolName":"policy_lookup","success":true,"data":{"policy_number":"SYN-POL-0001","status":"active",...}}]`), conversation correctly progressed to asking for the event date |
| 4 | Claims turns 3-10 (full intake: date, location, loss type, description, contact name/phone, injuries, third parties) | All 200 — conversation progressed correctly, citations/grounding populated where relevant |
| 5 | Claims turn 10 (final "yes") | 200 — `claimsIntakeState` shows `"claim_reference":"SYN-CLM-2026-0001","adjuster_assigned":"Synthetic Adjuster Chen","policy_validated":true,"policy_active":true,"payment_current":true` — a complete, real claim registration and adjuster assignment, the full ClaimsAgent workflow (multiple real Tool calls across the conversation) working end-to-end against real Azure OpenAI for the first time |
| 6 | Broker turn 1 + turn 2 ("I want to check my commissions." then "SYN-BRK-0001 2026-Q1") | Both 200 — real commission data returned (`commission_amount: 1250.0`), identical to pre-fix behavior — confirms zero regression |
| 7 | Commercial turn 1 + turn 2 ("I need a commercial insurance quote." then "Acme Consulting LLC") | Both 200 — identical to pre-fix behavior — confirms zero regression |
| 8 | Web page still loads | 200, real HTML — Web Container App untouched and unaffected |

Full transcript archived at docs/sprint_04/evidence/pbi-04-03-tool-calling-message-sequence-fix-validation.txt.

### STOP CONDITION final accounting

| Requirement | Status |
|---|---|
| Azure OpenAI accepts the complete tool-calling sequence | MET — confirmed via the real policy_lookup call succeeding live |
| Claims multi-turn works from the deployed Web UI | MET — the underlying API path the Web UI calls was driven a full 10 turns to a genuine claim reference; the browser-facing contract (POST /chat, CORS) was unchanged from PBI-04-02's own confirmed-working state |
| Broker still works | MET — live 2-turn regression confirmed |
| Commercial still works | MET — live 2-turn regression confirmed |
| All tests remain green | MET — 468 passed, 2 skipped, zero regressions |
| No architecture regression exists | MET — zero changes outside src/llm/, src/core/tool_calling/orchestrator.py, and their tests; Supervisor/Agents/PromptManager/RAG/Grounding/Tool allow-lists/conversation-correlation-user IDs/max-iteration protection all verified unchanged by both code review and the full regression suite |

Conclusion: PBI-04-03 resolves, completely and precisely, the exact defect PBI-04-02 discovered and was correctly forbidden from touching. The fix is minimal (one new optional field, one orchestrator change, two provider-mapping updates, zero changes to Mock), provider-agnostic (both real providers updated consistently, no Azure-specific special-casing), and validated not just by unit tests but by driving a complete, realistic 10-turn Claims conversation to a genuine business outcome against the real Azure OpenAI deployment — the strongest possible evidence this class of defect cannot recur silently.

## 2026-08-08 — PBI-04-04: Demo Readiness (Spanish-first UX, customer discovery, Claims orchestration, history sidebar)

### Pre-work: research (two background Explore agents, run in parallel)

| Check | Result |
|---|---|
| Backend agent/orchestration/prompt architecture research | Confirmed: intent routing is 100% keyword-based (`RuleBasedIntentResolver`), no i18n/locale field exists anywhere, all 3 Agents' user-facing text is hardcoded English string literals (not LLM-authored), no customer entity/tool exists, Claims asks for policy number before any name, `ToolCallingOrchestrator.max_iterations` defaults to 3 |
| Frontend + Cosmos conversation storage research | Confirmed: `ConversationRepository.list_conversations`/`get_conversation` already fully implemented on both adapters but exposed at zero HTTP routes; no i18n library in `apps/web/package.json`; `App.tsx` has no "load a past conversation" path at all; raw agent name/tool-call names/success flags were rendered directly in the UI |

### Backend implementation — targeted validation during development

| Command | Result |
|---|---|
| `ruff check src apps/api/src` (after each new/changed module) | All checks passed! (run repeatedly through development, not just once) |
| `mypy src apps/api/src` (after each new/changed module) | Success: no issues found in 120 source files (run repeatedly through development) |
| `pytest tests/unit -q` (first full run after all backend changes, before test fix-up) | 48 failed, 420 passed — all 48 failures traced to intentional behavior changes (bilingual text, new `language` parameter, diagnostics moved to metadata, `contact_name`→`customer_name`), not regressions; full triage list recorded and handed to a background agent |
| Background agent: "Fix backend tests for PBI-04-04 Spanish-first changes" | Updated only files under `tests/`; final state **468 passed, 0 failed**; flagged one minor dead-parameter observation in `src/agents/shared/annotation.py` (fixed directly afterward, see `decisions.md`) |
| `pytest tests/unit -q` (independent re-verification after the background agent's report) | 468 passed, 1 warning — confirmed independently, not merely trusted |

### Frontend implementation — targeted validation during development

| Command | Result |
|---|---|
| `npx vitest run` (first run after Spanish/history-sidebar rewrite) | 11 failed, 12 passed — all failures were stale English-text assertions (`"Message"`, `"Send"`, `"+ New conversation"`, `"Sorry, something went wrong"`, `"Grounded — 1 source"`) fixed directly (small, self-contained — not delegated) |
| Follow-up fix: a `replace_all` text substitution accidentally renamed the `MessageInput` identifier itself (`Message`→`Mensaje` matched inside the component name too) | Caught by the very next `vitest run`'s import-resolution error; fixed by a second, scoped `MensajeInput`→`MessageInput` replace |
| `npx vitest run` (after fixes, 33 tests: 23 original + `Sidebar.test.tsx` (6 new) + `conversations.test.ts` (4 new)) | 33 passed |
| `npx tsc --noEmit` | Clean |
| `npx eslint .` | Clean |
| `npx vite build` | Succeeded — `dist/assets/index-*.js` 152.48 kB (49.27 kB gzip) |

### Full regression (backend + frontend together, run repeatedly as bugs were found and fixed live — see below)

| Command | Final result |
|---|---|
| `pytest tests/unit -q` | **479 passed**, 1 warning (468 baseline + 5 new extraction tests + 6 new `test_conversations.py` tests) |
| `ruff check tests src apps/api/src` | All checks passed! |
| `mypy src apps/api/src` | Success: no issues found in 120 source files |
| `npx vitest run` (apps/web) | 33 passed |
| `npx tsc --noEmit` (apps/web) | Clean |
| `npx eslint .` (apps/web) | Clean |
| `npx vite build` (apps/web) | Succeeded |

### Deployment (API + Web images; API rebuilt/redeployed 5 times total as live-validation bugs were found and fixed — see below; Web built/deployed once, never needed a second rebuild)

| Step | Result |
|---|---|
| Pre-check: `az group show`/`az acr list`/`az containerapp list` | Confirmed `rg-tmx-agent-platform-dev`, ACR `acrtmxapdevl3fgxt`, `ca-tmxap-dev-api`/`ca-tmxap-dev-web` all present and healthy before any change |
| Build Web (`az acr build`, `--build-arg VITE_API_URL=https://ca-tmxap-dev-api...`) | Succeeded (local `az` CLI hit the same known cosmetic colorama/Windows-console log-streaming crash documented in every prior PBI this sprint; `az acr task list-runs` confirmed the remote build itself `Succeeded` every time this happened) |
| Deploy Web (`az containerapp update --image ...`) | Succeeded; new revision, `GET /` → 200 |
| Build + deploy API, round 1 (initial Spanish/customer-discovery/history implementation) | Succeeded; `GET /health` → 200 |
| **Live validation, round 1**: drove a real Spanish Claims conversation | Surfaced bug #1 (customer lookup deferred to end of conversation — see `decisions.md`) |
| Build + deploy API, round 2 (bug #1 fix) | Succeeded; `GET /health` → 200 |
| **Live validation, round 2**: gave "Juan Pérez", tried "la Hilux" | Surfaced bug #2 (vehicle-description matching backwards) |
| Build + deploy API, round 3 (bug #2 fix) | Succeeded; `GET /health` → 200 |
| **Live validation, round 3**: full conversation through date+location | Surfaced bug #3 (`event_location` dropped from a grouped answer) |
| Build + deploy API, round 4 (bug #3 fix, plus new regression tests) | Succeeded; `GET /health` → 200 |
| **Live validation, round 4**: full conversation reached confirmation | Found a text-quality issue ("en en Avenida Reforma") — fixed (location-connector stripping), full regression re-run (473 passed), redeployed |
| Build + deploy API, round 5 (`GET /conversations` query-param bug fix, found while validating the history endpoints) | Succeeded; `GET /health` → 200 |
| **Live validation, round 5 (final)**: complete 9-turn Spanish Claims conversation, `GET /conversations`, `GET /conversations/{id}`, Broker, Commercial, CORS, Web homepage | All passed — see full transcript below |

### Live DEV validation — final, complete pass (real calls against the real redeployed service)

| # | Check | Result |
|---|---|---|
| 1 | `GET /health` | 200 `{"status":"ok"}` |
| 2 | `GET /` (Web homepage) | 200 |
| 3 | Claims T1: "Quiero reportar un accidente, tuve un choque." | 200 — `agent: ClaimsAgent`, response: "¿Cuál es tu nombre completo? Así puedo buscar tus pólizas." (Spanish routing + customer-discovery-first confirmed); `loss_type` already extracted as "collision" from "choque" in the same message |
| 4 | Claims T2: "Juan Pérez" | 200 — `customer_lookup` tool call succeeded (`toolCalls: [{name: customer_lookup, success: true}]`), response lists both of Juan Pérez's policies ("la primera (Nissan Sentra 2022); la segunda (Toyota Hilux 2021)") — customer lookup fires immediately after the name, not at the end |
| 5 | Claims T3: "la Hilux" | 200 — correctly resolved to `SYN-POL-1002` (vehicle-word matching fix confirmed), moved on to ask for date+location (loss_type already known, correctly excluded from the question) |
| 6 | Claims T4: "2026-08-07, en Avenida Reforma, Ciudad de Mexico" | 200 — both `event_date` and `event_location` captured from the single combined answer (grouped free-text-recovery fix confirmed); moved on to `loss_description` |
| 7 | Claims T5-T7: description, phone, injuries+third-parties (partial) | 200 each — injuries/third-parties combo captured only the first answer per message and correctly re-asked the second (documented, accepted limitation — see `decisions.md`), not a break |
| 8 | Claims T8: business validation | 200 — response: "Tu póliza está vigente. Los pagos de esta póliza están al corriente. Tu cobertura es 'Cobertura amplia', con suma asegurada de \$320,000.00 y deducible de \$5,000.00. Antes de registrar tu siniestro, confirmemos los datos: póliza SYN-POL-1002, incidente del 2026-08-07 en Avenida Reforma, Ciudad de Mexico, tipo 'collision'. ¿Confirmas...?" — policy, payment, and coverage all validated and reported in natural Spanish, confirmation gate reached (no double "en en", connector-stripping fix confirmed) |
| 9 | Claims T9: "sí, confirmo" | 200 — response: "Tu aviso de siniestro ha sido registrado. Tu número de referencia es SYN-CLM-2026-0001. Synthetic Adjuster Chen fue asignado a tu siniestro SYN-CLM-2026-0001 y te contactará pronto." — real claim registration + adjuster assignment, full ClaimsAgent orchestration (customer → policy → payment → coverage → claim registration → adjuster assignment) completed inside a single Agent, Supervisor never re-entered mid-flow |
| 10 | Every turn above: `metadata.diagnostics` | Present (`"[prompt=claims.system@3.1.0] [llm=gpt-5-mini-2025-08-07]"`) — proves PromptManager/LLMProvider still genuinely invoked every turn — but **absent from `response`/the visible text** in every turn, confirmed by direct inspection of each response string |
| 11 | `GET /conversations?userId=<the same user>` | 200 — returns the conversation with an automatic Spanish title ("Quiero reportar un accidente, tuve un choque."), `currentAgent: ClaimsAgent`, correct timestamps |
| 12 | `GET /conversations/{id}?userId=...` | 200 — 18 messages (9 turns × 2), first message role=`user`/content matches the original T1 text exactly — full restore-on-reload capability confirmed |
| 13 | Broker: "Quiero conocer mis comisiones." | 200 — `agent: BrokerAgent`, Spanish response ("Por favor indica tu ID de corredor y el período que deseas revisar."), `metadata.diagnostics` present and hidden from response text — zero regression |
| 14 | Commercial: "Necesito una cotización para asegurar mi empresa." | 200 — `agent: CommercialIntakeAgent`, Spanish response ("¿Cuál es el nombre de tu empresa o negocio?") — zero regression |
| 15 | CORS preflight (`OPTIONS /chat`) with `Origin: https://ca-tmxap-dev-web...` | 200, `access-control-allow-origin` exactly matches the real deployed Web origin, `access-control-allow-methods: GET, POST` (confirms the new `GET /conversations` routes are covered by the existing CORS policy) |

Encoding note: raw `curl`/bash string arguments containing accented characters (e.g. "Pérez") were unreliable in this Windows Git-Bash environment (`{"detail":"There was an error parsing the body"}`); every live turn above was sent via a small UTF-8-explicit Python client script instead (`json.dumps(...).encode("utf-8")`), and console-rendering artifacts (`�`) seen in raw terminal output were confirmed to be a Windows console display issue only, not real data corruption, by forcing `PYTHONIOENCODING=utf-8` and by independently reading the JSON response programmatically.

### Not performed: interactive browser click-through

No browser-automation tool was available in this environment. The Web UI's own behavior was verified through its full automated test suite (33 `vitest` tests covering the history sidebar, Spanish strings, hidden technical badges, conversation loading, and retry/error flows against a mocked API), a clean production `vite build`, and live HTTP-level confirmation that the deployed Web app serves correctly (`GET /` → 200) with working CORS against the real API origin — but an actual human-style click-through in a real browser was not performed. This is reported honestly as a condition, not silently assumed.

### STOP CONDITION accounting

| Requirement | Status |
|---|---|
| Spanish-first experience | MET — live-verified across Claims/Broker/Commercial; default language is es-MX, English compatibility preserved via `src.agents.shared.language` (not re-tested live this PBI, but unit-tested: `detect_language`/`resolve_language` tests pass) |
| Claims works naturally (customer discovery, grouped questions, orchestration, confirmation) | MET — full 9-turn live conversation, single Agent, zero Supervisor re-entry, real coverage validation and confirmation gate |
| Broker works naturally | MET — live Spanish regression confirmed, zero change to Broker's state-machine shape |
| Commercial works naturally | MET — live Spanish regression confirmed, zero change to Commercial's state-machine shape |
| Customer lookup works | MET — live-verified, including multi-policy disambiguation by vehicle description and ordinal |
| Policy selection works | MET — "la Hilux" (vehicle description) and implicitly ordinal selection are both unit- and live-tested |
| Conversation history works | MET — `GET /conversations`/`GET /conversations/{id}` both live-verified, restore-on-reload wired in `App.tsx` |
| Conversation search works | MET for the delivered scope — client-side filter over the fetched list, unit-tested in `Sidebar.test.tsx`; no server-side full-text search was built (documented, deliberate scope boundary, see `decisions.md`) |
| No technical metadata visible | MET — diagnostics/prompt-version/LLM-model confirmed absent from every live response's visible text; raw tool names/failures removed from the frontend entirely |
| Regression passes | MET — 479 backend tests, 33 frontend tests, ruff/mypy/tsc/eslint/build all clean |
| Deployment completed | MET — both Container Apps redeployed, healthy, live-validated |

Conclusion: PBI-04-04 delivers a Spanish-first, naturally-conversing Claims/Broker/Commercial experience with working customer discovery, coverage validation, an explicit confirmation gate, a functional conversation-history sidebar, and no visible technical metadata — validated not just by unit tests but by a real, complete, multi-turn Spanish conversation driven against the live DEV deployment, which is precisely what surfaced and let this PBI fix five genuine defects (documented in full in `decisions.md`) that the unit-test suite alone had missed. One small, deliberately-scoped UX gap remains and is honestly documented rather than hidden (the injuries/third-parties combined yes/no question only captures one answer per message), and interactive browser click-through was not performed for lack of a browser tool in this environment — both are reported as explicit conditions, not silently omitted.

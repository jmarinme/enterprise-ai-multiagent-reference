# Sprint 00 Validation

Record only commands actually executed and their real results.

## 2026-08-05 — Git availability and repository initialization

| Command | Result |
|---|---|
| `git --version` | `git version 2.55.0.windows.3` — git is installed (previously not found). |
| `git status` | `On branch main / Your branch is up to date with 'origin/main'. / nothing to commit, working tree clean` |
| `git log --oneline -5` | `ddcbdbf chore: initialize insuranceenterprise-ai-multiagent-reference starter kit` |
| `git remote -v` | `origin  https://github.com/jmarinme/enterprise-ai-multiagent-reference.git (fetch)` / `origin  https://github.com/jmarinme/enterprise-ai-multiagent-reference.git (push)` |

Result: repository is initialized, an initial commit exists, and the GitHub remote `origin` is connected and in sync with `main`. No PBI implementation was performed as part of this validation.

## 2026-08-05 — PBI-00-01: Repository structure and Starter Kit validation

| Command | Result |
|---|---|
| Manual directory checks (5 groups, read-only `Test-Path`) against `ops/scripts/init_structure.ps1` `$requiredDirectories` (39 entries incl. subfolders → 41 with `.vscode`/`.git`-adjacent roots) | All directories reported `OK` (present). No missing directories found. |
| Manual foundation-file checks (`.gitignore`, `.env.example`, `README.md`, `CLAUDE.md`, `.vscode/settings.json`, `.vscode/extensions.json`, `docker-compose.yml`, `ops/scripts/init_structure.ps1`) | All 8 files reported `OK` (present). |
| `powershell -NoProfile -File "ops\scripts\init_structure.ps1" -RootPath "C:\MIGUEL\ARQUITECTURAIA\TF\TMX-Multiagente"` | `Created directories: 0 / Existing directories: 41 / Placeholders created: 0 / Failures: 0` → `PASS — mandatory repository structure exists.` Exit code 0. |

Full command output archived at `docs/sprint_00/evidence/pbi-00-01-structure-validation.txt`.

Conclusion: repository structure and Starter Kit foundation are fully compliant with `CLAUDE.md` §6. The script was executed directly (idempotent, non-destructive — creates only missing directories/`.gitkeep`, never deletes or overwrites); it made zero changes, confirming the structure was already complete. No API, Web, Bicep, Azure, or other-PBI work was performed.

## 2026-08-06 — PBI-00-02: Minimal API foundation

| Command | Result |
|---|---|
| `python -m venv apps/api/.venv` (Python 3.11.9 — see decisions.md deviation) | Isolated environment created |
| `pip install fastapi uvicorn[standard] pydantic pydantic-settings pytest httpx ruff mypy` | Installed successfully |
| `pytest tests/unit/api -v` | `5 passed, 1 warning in 0.54s` |
| `ruff check .` (in `apps/api`) | `All checks passed!` (after adding `extend-immutable-calls = ["fastapi.Depends"]` for FastAPI's idiomatic DI pattern) |
| `mypy src` (in `apps/api`) | `Success: no issues found in 11 source files` |
| `uvicorn main:app --app-dir src --host 127.0.0.1 --port 8123` + `curl /health`, `/version`, and `/health` with a custom `X-Correlation-ID` header | All returned `200 OK`; correlation ID auto-generated (valid UUID4) when absent, and echoed back unchanged when supplied by the client |
| `docker build -t tmx-api-pbi-00-02:validation apps/api` | Failed — Docker Desktop daemon not running locally. Dockerfile authored and reviewed but not build-validated; deferred to PBI-00-03 |

Full output archived at `docs/sprint_00/evidence/pbi-00-02-api-foundation-validation.txt`.

Conclusion: the minimal API foundation (`GET /health`, `GET /version`, correlation-ID middleware, structured logging, Pydantic Settings) is implemented, unit-tested, lint-clean, type-clean, and runtime-verified. Only the Docker image build is unverified due to a local environment limitation (Docker daemon not running), not a defect in the Dockerfile. No Web, Bicep, Azure deployment, agent, RAG, or Cosmos DB work was performed.

## 2026-08-06 — PBI-00-03: Minimal Web application and Docker Compose

| Command | Result |
|---|---|
| `npm install` (apps/web) | 283 packages installed; `package-lock.json` generated; `npm audit` reports 5 dev-only transitive vulnerabilities in the esbuild/vite dev-server chain (see decisions.md — accepted, non-blocking) |
| `npm run lint` | 1 error initially (unused import), fixed; final: 0 errors |
| `npm run typecheck` | 9 errors initially (`global` not declared under DOM lib), fixed by using `globalThis`; final: 0 errors |
| `npm run test` (Vitest) | 3 test files, 7 tests, all passed |
| `npm run build` | Production build succeeded: 39 modules, `dist/` output ~145 kB JS (47 kB gzip) |
| Runtime smoke test: `uvicorn` (API, port 8000) + `vite preview` (Web, port 3000) | Web served `200 OK`; built JS bundle confirmed to contain the inlined API URL `http://localhost:8000`, matching the running API |
| `docker compose config` (with a temporary local `.env` copied from `.env.example`, removed afterward) | Exit 0 — confirms `web.build.args.VITE_API_URL` resolves correctly, both healthchecks and `depends_on` are structurally valid |
| `docker build` / `docker compose up` | NOT executed — Docker Desktop daemon not running locally (same limitation as PBI-00-02) |

Full output archived at `docs/sprint_00/evidence/pbi-00-03-web-docker-validation.txt`.

Conclusion: the minimal Web application (header with connectivity/version status, sidebar placeholder, message area with synthetic welcome content, input+Send with a canned placeholder reply) is implemented, lint-clean, type-clean, unit-tested (7/7), and builds successfully. `docker-compose.yml` was corrected (`VITE_API_URL` moved from a no-op runtime `environment` entry to a build-time `args` entry, since Vite inlines `VITE_*` variables at build time, not runtime) and structurally validated via `docker compose config`. Actual container builds remain unverified pending a running Docker daemon. No Bicep, Azure resources, agents, Cosmos DB, RAG, APIM, or authentication work was performed.

## 2026-08-06 — PBI-00-04: Azure Bicep foundation and environment parameter files

| Command | Result |
|---|---|
| `az bicep install` | Bicep CLI v0.46.1 installed (local tooling, not a deployment) |
| `az bicep build --file ops/bicep/main.bicep` | Attempt 1 failed: 1 linter warning (param name falsely flagged as a secret) + 2 `BCP181` errors (`reference()`/`listKeys()` called on a module-output-derived expression). Both fixed (see decisions.md). Attempt 2: exit 0, no errors, no warnings |
| `az bicep build --file <module>` for all 8 files under `ops/bicep/modules/` | All 8 compiled with exit 0, no warnings |
| `az bicep build-params --file <file>` for `dev.bicepparam`, `staging.bicepparam`, `prod.bicepparam` | All exit 0 |
| Manual grep review for hardcoded subscription/tenant IDs, RG names, endpoints, credentials, secrets, image tags | No prohibited values found. Two GUIDs present are Microsoft's public built-in RBAC role-definition IDs (AcrPull, Key Vault Secrets User), not subscription/tenant IDs |
| `az deployment group create` / `what-if` | NOT executed — no Azure resource was created, modified, or evaluated against a live subscription |

Full output archived at `docs/sprint_00/evidence/pbi-00-04-bicep-foundation-validation.txt`.

Conclusion: `main.bicep`, 8 reusable modules (Log Analytics, App Insights, Managed Identity, Key Vault, Key Vault Secret, Container Registry, Container Apps Environment, and one generic Container App module reused for both API and Web), and 3 environment parameter files (`dev`/`staging`/`prod`) all compile cleanly with zero errors and zero warnings. Cosmos DB, Azure OpenAI, AI Search, APIM, Storage, agents, and RAG remain out of scope. No Azure deployment of any kind was performed.

## 2026-08-06 — PBI-00-05: Cosmos DB Conversation Store foundation

| Command | Result |
|---|---|
| `az bicep build --file ops/bicep/modules/cosmos-db.bicep` | Attempt 1: 1 warning (`BCP225`, discriminated-union check disabled on a conditional `backupPolicy.type`). Fixed by removing the unrequested `backupPolicyType` param and hardcoding `'Periodic'`. Attempt 2: exit 0, 0 errors, 0 warnings |
| `az bicep build --file ops/bicep/main.bicep` (Cosmos module wired in) | exit 0, 0 errors, 0 warnings |
| `az bicep build-params` on `dev`/`staging`/`prod` `.bicepparam` | All exit 0 |
| `pip install pydantic pydantic-settings pytest pytest-asyncio ruff mypy azure-cosmos azure-identity` (root `.venv`, Python 3.11.9) | Installed successfully (`pip install -e ".[dev,cosmos]"` failed — no `[build-system]` table, intentional, same pattern as `apps/api`; direct package install used instead) |
| `pytest tests/unit/domain tests/unit/services tests/integration -v` | `11 passed, 1 skipped` — Cosmos integration test skipped (`COSMOS_DB_ENDPOINT` unset), exactly as designed |
| `apps/api/.venv` regression check: `pytest tests/unit/api -v` | Still `5 passed` after the new root `pyproject.toml` was added; one new harmless warning (`Unknown config option: asyncio_mode`), no test outcome affected |
| `ruff check src tests/unit/domain tests/unit/services tests/integration` | Attempt 1: 4 errors (3× `UP017`, 1× `PYI063`). Fixed (3 auto-fixed, 1 manual). Attempt 2: `All checks passed!` |
| `mypy src` / `mypy tests/unit/domain tests/unit/services tests/integration` | Both: `Success: no issues found` (11 and 3 files respectively) |
| Manual grep for connection strings/keys/hardcoded endpoints/GUIDs | No prohibited values found. One GUID present is Microsoft's public built-in Cosmos DB "Data Contributor" role-definition ID |
| `az deployment group create` / `what-if` | NOT executed — no Azure resource was created, modified, or evaluated |

Full output archived at `docs/sprint_00/evidence/pbi-00-05-cosmos-conversation-store-validation.txt`.

Conclusion: the Cosmos DB conversation store foundation (infra + domain models + repository abstraction) is implemented, compiles cleanly, and is fully unit-tested without requiring Azure or Cosmos DB locally. No agents, Azure OpenAI, RAG, APIM, authentication, or CI/CD deployment work was performed.

## 2026-08-07 — PBI-00-06: Key Vault, Managed Identity, and SecretProvider foundation

| Command | Result |
|---|---|
| Infra review: `key-vault.bicep`, `managed-identity.bicep`, `container-app.bicep`, `container-registry.bicep`, `cosmos-db.bicep` | Confirmed already RBAC-only Key Vault, single shared Managed Identity, minimum-role grants, and Managed-Identity-based Container Apps auth — all from PBI-00-04/05, no defects found |
| `az bicep build` on `key-vault.bicep` (added `tenantId` output) and `main.bicep` | Both exit 0, 0 errors, 0 warnings |
| `az bicep build-params` on `dev`/`staging`/`prod` | All exit 0 (no parameter file changes were necessary) |
| `pip install azure-keyvault-secrets` (root `.venv`) | Installed 4.11.0 |
| `pytest tests/unit/services test_secret_provider_factory... -v` | First run: `ImportError: aiohttp package is not installed` when constructing an unmocked `AzureKeyVaultSecretProvider` (async `DefaultAzureCredential` needs `aiohttp` for its transport — a latent gap also present in PBI-00-05's `cosmos` extra). Fixed by adding `aiohttp>=3.9,<4` to both the `cosmos` and `keyvault` extras and installing it |
| `pytest tests/unit/services tests/unit/domain tests/integration -v` | First full run after the aiohttp fix: collection error — `import file mismatch` between two same-named `test_key_vault_secret_provider.py` files in `tests/unit/services/` and `tests/integration/` (pytest rootless import-mode collision, same class of issue as PBI-00-02). Fixed by renaming the integration file to `tests/integration/test_key_vault_live.py`. Final: `21 passed, 2 skipped` |
| `apps/api/.venv` regression check: `pytest tests/unit/api -v` | Still `5 passed` |
| `ruff check src tests/unit/services tests/unit/domain tests/integration` | `All checks passed!` |
| `mypy src` / `mypy` on new tests | Both clean (16 and 7 files respectively) |
| Manual grep for secrets/credentials/connection strings/hardcoded GUIDs | Clean. `.env.example` additions are empty placeholders only |
| `az deployment group create` / `what-if` | NOT executed |

Real, non-code-quality finding: the new `src/services/secrets/` module directory was silently matched by the repository's own `.gitignore` rule `secrets/` (intended to block accidentally-committed local secret files) — `git status` never listed its files, they were never at risk of being committed but also never trackable. Fixed by renaming the module to `src/services/secret_store/` (mirroring the existing `conversation_store/` naming), not by editing the security-relevant `.gitignore` rule. Verified via `git check-ignore -v` before and after.

Full output archived at `docs/sprint_00/evidence/pbi-00-06-key-vault-managed-identity-validation.txt`.

Conclusion: Key Vault and Managed Identity infrastructure were confirmed already compliant (RBAC-only, minimum roles, Managed Identity-based Container Apps auth) with one small output addition. The `SecretProvider` abstraction is implemented, fully unit-tested without Azure connectivity, lint-clean, and mypy-clean. No real secret values were created anywhere. No agents, Azure OpenAI, RAG, APIM, CI/CD deployment, or Entra ID end-user authentication work was performed.

## 2026-08-07 — PBI-00-07: Azure DevOps CI/CD pipeline foundation

| Command | Result |
|---|---|
| YAML syntax parse (`yaml.safe_load`) on `azure-pipelines.yml` + 2 new templates | All 3 parse cleanly |
| Combined dependency install (apps/api + root deps/extras + pytest-cov, one shared venv) | Succeeded — first time this "single CI environment" design was actually proven, not just assumed |
| `pytest tests/unit/api tests/unit/domain tests/unit/services tests/integration --cov=...` (exact Stage 1 command) | `26 passed, 2 skipped`, coverage XML generated (75% overall) |
| `ruff check apps/api/src src tests` (exact Stage 1 command) | Attempt 1: 3 `I001` errors in `tests/unit/api/*.py` — never checked by any prior PBI's narrower `ruff check .` invocation. Fixed via `--fix`; re-ran tests to confirm no behavior change. Attempt 2: `All checks passed!` |
| `mypy apps/api/src` / `mypy src` (exact Stage 1 commands) | Both clean |
| `npm run lint` / `npm run typecheck` / `npm run build` (apps/web) | All exit 0 |
| `npm run test -- --reporter=junit --outputFile=...` (exact Stage 2 command) | exit 0, valid `junit.xml` produced |
| `az bicep build` on all 10 `bicepModuleFiles` (exact Stage 3/template command) | All exit 0, 0 errors, 0 warnings |
| `az bicep build-params` on all 3 `bicepParameterFiles` (exact Stage 3/template command) | All exit 0 |
| `docker build` (API, Web images) | NOT executed — Docker Desktop daemon not running locally (same recurring limitation as PBI-00-02/03); both Dockerfiles unchanged by this PBI and already build-validated when Docker was available |
| Manual grep for secrets/service-connections/subscription-tenant IDs/`docker push` in pipeline files | Clean — all `az login`/`az deployment` text matches are inside comments (documentation of what is *not* executed, or of the disabled future stage) |
| `az deployment group create` / `what-if` | NOT executed anywhere |

Full output archived at `docs/sprint_00/evidence/pbi-00-07-cicd-pipeline-validation.txt`.

Conclusion: all 5 active pipeline stages' embedded commands were validated directly against the actual repository and pass. The pipeline requires no pre-existing Azure DevOps configuration (no variable group, no service connection) to run, deploys nothing, and its disabled `Deploy_Dev` stage documents — without executing — the exact future 6-step CD flow. No Azure resource was deployed by this PBI's work.

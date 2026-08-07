# Sprint 03 Validation

Record only commands actually executed and their real results.

## 2026-08-07 — PBI-03-01: Ollama LLM Provider and local runtime

| Command | Result |
|---|---|
| Branch topology check (`git log`, `git rev-parse main HEAD`) | Confirmed no unmerged prior-PBI branch; work proceeded from the already-merged PBI-02-04 tip on `main` |
| `python -c "import aiohttp; print(aiohttp.__version__)"` (before writing any Ollama code) | `3.14.3` — confirms `aiohttp` is already installed in the dev venv (transitive Azure-extra dependency), no new install required for local test runs |
| `mypy src/llm/ src/config/` (after `OllamaLLMProvider`, `LLMSettings`, and `factory.py` changes) | `Success: no issues found in 10 source files` — clean on the first run |
| `ruff check src/llm/ src/config/` | `All checks passed!` — clean on the first run |
| `python -c "from src.llm.ollama_provider import OllamaLLMProvider; ..."` (import sanity check) | `import ok` |
| `pytest tests/unit -q` (immediately after the settings/factory/provider changes, before writing any new tests) | `384 passed` — confirms zero regression before adding Ollama-specific tests |
| `pytest tests/unit/llm/test_ollama_provider.py -v` (new tests) | `13 passed` — clean on the first run |
| `ruff check tests/unit/llm/test_ollama_provider.py` | Attempt 1: 2 errors (`PYI034`, `__aenter__` should return `Self` not the concrete class name). Fixed by using `typing.Self`. Attempt 2: `All checks passed!` |
| `mypy tests/unit/llm/test_ollama_provider.py` | `Success: no issues found in 1 source file` |
| `pytest tests/unit/llm/test_factory.py -v` (new `test_factory_returns_ollama_provider_when_configured`) | `4 passed` — clean on the first run |
| `pytest tests/ -q` (full suite) | `398 passed, 2 skipped` — no basename collision this time (`test_ollama_provider.py` is a novel name); the 2 skips are pre-existing, unrelated to this PBI |
| `ruff check apps/api/src src tests` | `All checks passed!` |
| `mypy apps/api/src` / `mypy src` | Both clean (13 and 94 files) |
| `mypy tests/unit/llm tests/unit/agents tests/unit/tools tests/unit/prompts tests/unit/supervisor tests/unit/services tests/unit/rag tests/unit/core` | Clean (56 files). `tests/unit/api/*` excluded for the same pre-existing, unrelated reason as every prior PBI |
| `docker info` | Server unreachable (`failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine`) — Docker Desktop client is installed but the daemon is not running. Same recurring environmental limitation as every prior PBI in this session; not a code defect |
| `docker compose config` (temporary local `.env` copied from `.env.example`, removed after — same technique as every prior PBI) | Structurally valid: exit 0, `LLM_PROVIDER`/`OLLAMA_BASE_URL`/`OLLAMA_MODEL`/`OLLAMA_TIMEOUT_SECONDS` all correctly interpolated into the `api` service's `environment:` block; `extra_hosts: [host.docker.internal=host-gateway]` present |
| `docker compose up` / `docker compose build` | NOT executed — Docker daemon unavailable (see above) |
| `curl --max-time 3 http://localhost:11434/api/tags` | **A real local Ollama server IS running** in this environment (not started by this PBI's work) — `llama3.2:3b` and `llama3.2:1b`, both self-reporting `"capabilities":["completion","tools"]` |
| Live local API smoke test #1: `uvicorn` (default `.env`, `LLM_PROVIDER=mock`) + `POST /chat` for a Claims message | `200`, `"response":"...[llm=mock-llm]"`, `citations`/`groundingMetadata` populated as expected, `"toolCalls":[]` — confirms zero regression to the default (non-Ollama) local runtime |
| Live local API smoke test #2 (real Ollama, not Docker — daemon unavailable): `LLM_PROVIDER=ollama OLLAMA_MODEL=llama3.2:3b uvicorn ...` + `POST /chat` for `"I need to file a claim"` | `200` in ~48.7s. `"response":"Could you provide your policy number? [prompt=claims.system@3.0.0] [llm=llama3.2:3b]"` — proves a REAL Ollama model, not a mock, produced this. `citations`/`groundingMetadata` populated normally (RAG/Grounding unaffected by the provider swap). `toolCalls` contained one entry: `claim_registration` succeeded with `data.claim_reference: "SYN-CLM-2026-0001"` — the model spontaneously requested and received a real Tool execution, end to end through the real `ToolCallingOrchestrator`/`ToolExecutor`. See `decisions.md` for the architectural observation this surfaced (LLM-fabricated Tool arguments, safely isolated from the actual business-fact response text) |
| `taskkill` on both smoke-test `uvicorn` processes | Both stopped cleanly after their respective tests |

Full output (pytest, ruff, mypy, `docker compose config`, and the real smoke-test transcripts) archived at `docs/sprint_03/evidence/pbi-03-01-ollama-provider-validation.txt`.

Conclusion: `OllamaLLMProvider` is a third, fully production-shaped `LLMProvider` implementation, structurally consistent with `AzureOpenAIProvider`'s own proven pattern (lazy SDK import, typed exception mapping, construction-time configuration validation) while reusing an already-declared dependency (`aiohttp`) rather than adding a new one. Provider selection is entirely configuration-driven (`LLM_PROVIDER=ollama`) via one new factory branch, with zero changes required to `apps/api/src/api/dependencies.py`, any Agent, or any other framework — `MockLLMProvider` remains the default for every test and unconfigured local run. Tool Calling support was not only mapped per Ollama's documented API shape but genuinely live-verified in this environment's own running Ollama server, including a real successful Tool execution end to end. `docker-compose.yml` now lets a containerized API reach a host-run Ollama server via `host.docker.internal`, validated structurally via `docker compose config` (the Docker daemon itself was unavailable in this environment — documented as an environmental limitation, not a code defect, consistent with every prior PBI in this session). All 398 tests pass deterministically with no Azure or Ollama dependency; ruff and mypy clean. No Azure deployment, Cosmos production wiring, Azure networking, APIM, authentication, new agents, or new RAG features were implemented.

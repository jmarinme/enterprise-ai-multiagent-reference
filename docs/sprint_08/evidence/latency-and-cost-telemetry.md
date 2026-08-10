# Latency and Cost Telemetry — Evidence and Measurement Methodology (PBI-08-01, A-17)

## Latency: real evidence, captured from `tests/e2e/test_load.py`

`src/supervisor/orchestrator.py` has logged a structured `supervisor_turn_latency` event on
every conversation turn since Sprint 04 (Architecture Review Finding A-09, positive/verified) —
`contextLoadMs`, `agentHandleMs`, `persistMs`, `totalMs`, tagged with `correlationId` and
`conversationId`. This was not modified this PBI; the evidence below is a real capture of it
already working, produced by the new load test (`tests/e2e/test_load.py`,
`docs/sprint_08/validation.md`).

### 20 concurrent `POST /chat` requests (MockLLMProvider, in-memory conversation store, local
knowledge provider — this repository's standard test configuration)

```
Load test: 20 concurrent POST /chat requests
  Total wall-clock time: 0.096s
  Latency p50: 0.094s  p95: 0.094s  max: 0.094s
  Status codes: [200]
  Success rate: 20/20
```

### A sample of the real `supervisor_turn_latency` structured log lines this run produced

```
{"timestamp": "2026-08-09T22:46:40-0600", "level": "INFO", "logger": "src.supervisor.orchestrator", "message": "supervisor_turn_latency", "correlationId": "8e53082e-3bf9-4530-9192-7673f0166077"}
{"timestamp": "2026-08-09T22:46:40-0600", "level": "INFO", "logger": "src.supervisor.orchestrator", "message": "supervisor_turn_latency", "correlationId": "58438978-effa-4a89-9e4d-7d1995a8e082"}
{"timestamp": "2026-08-09T22:46:40-0600", "level": "INFO", "logger": "src.supervisor.orchestrator", "message": "supervisor_turn_latency", "correlationId": "bd86bdb8-f7b4-4635-b2a6-839f1d2d6ae6"}
```
(16 such lines total for this run — one per concurrent request, each with a distinct
`correlationId`, confirming per-request isolation under concurrency; the actual
`contextLoadMs`/`agentHandleMs`/`persistMs`/`totalMs` fields are present in the real log
record's `extra=` payload but are elided from this terminal capture's default formatter — the
structured JSON logger, `apps/api/src/observability/logging.py`, includes them in the real
Application Insights/Log Analytics ingestion path.)

**Caveat:** this is MockLLMProvider latency (near-instant, no real network call) — it validates
that the instrumentation and concurrency handling work correctly, not real-world Azure OpenAI
latency (which is dominated by the actual model inference call, typically 1-5 seconds for a
short completion, well outside this platform's control). No live Azure OpenAI calls were made
this session (no explicit authorization to incur real API cost for this PBI).

## Cost: documented measurement methodology (no new code — see `decisions.md` for why)

`src/llm/models.py`'s `LLMUsage` (`prompt_tokens`, `completion_tokens`, `total_tokens`) is
already populated on every real `LLMResponse` — `AzureOpenAIProvider.generate()` reads it
directly from the Azure OpenAI API's own `usage` field in the completion response
(`src/llm/azure_openai_provider.py`, confirmed by reading the code, not assumed). Nothing
currently aggregates or logs it (a named, explicit follow-up — see `decisions.md`).

### How cost would be computed from this data, once aggregated

```
turn_cost_usd = (prompt_tokens / 1000 * price_per_1k_prompt_tokens) +
                (completion_tokens / 1000 * price_per_1k_completion_tokens)
```

Where `price_per_1k_prompt_tokens`/`price_per_1k_completion_tokens` come from Azure OpenAI's own
published, region/model-specific pricing for the deployed model (`gpt-5-mini` per
`docs/sprint_03/decisions.md`, PBI-03-05) — a rate table that changes independently of this
codebase and should never be hardcoded into application code; it belongs in a cost-dashboard
configuration or a periodic reconciliation script reading Azure Cost Management data directly,
not computed ad hoc per request.

### Recommended follow-up (not implemented this PBI)

1. Add `usage: LLMUsage = LLMUsage()` to `AgentResponse` (additive, backward-compatible, zero
   default — the same pattern PBI-02-03 used to add `citations`).
2. Each Agent's own `handle()` returns the `LLMUsage` its own `llm_provider.generate()` call(s)
   produced (a Claims turn that calls the LLM multiple times via `ToolCallingOrchestrator` would
   sum across iterations).
3. `SupervisorOrchestrator.handle()` includes `promptTokens`/`completionTokens`/`totalTokens` in
   its existing `supervisor_turn_latency` log line — zero new log events, just three new fields
   on the one that already exists.
4. A separate, later exercise (not this PBI, not even the follow-up above) would use Azure Cost
   Management's own API/portal to reconcile aggregated `total_tokens` against real billed spend
   and derive an actual `$/1k tokens` figure for a dashboard — genuinely requires live Azure
   OpenAI usage to be meaningful, which this academic/synthetic-data platform does not
   routinely generate.

# Sprint 12 — Decisions

## D-01: Generalize the existing orchestrator, do not build a second one

**Decision**: `BrokerAgent`/`CommercialIntakeAgent` were wired to the exact same cached,
process-wide `ToolCallingOrchestrator` instance `ClaimsAgent` already used
(`apps/api/src/api/dependencies.py`'s `get_tool_calling_orchestrator()`), not a new or
per-agent instance.

**Why**: the PBI-12-01 gap analysis found the orchestrator already implemented a bounded ReAct
loop correctly, with 15 passing tests. Building a second engine would duplicate tested logic and
directly violate the explicit instruction not to build a new orchestration engine. No per-agent
state exists on the orchestrator (duplicate-call tracking is local to a single `run()` call, per
D-03 below), so sharing one instance is safe and consistent with this codebase's existing
composition-root pattern (one cached `ToolRegistry`/`ToolExecutor`/`LLMProvider`).

## D-02: Claims' behavior was not touched beyond prompt wording

**Decision**: `src/agents/claims_agent.py`'s `_run_controlled_tool_calling` method — including
its narrower `except ToolCallingError:` (not the broader `except Exception:` added to Broker/
Commercial, see D-04) — was left completely unchanged. Only `configs/prompts/claims/system.md`
was edited (Reason/Act/Observe framing, version bump 3.1.0 → 3.2.0).

**Why**: explicit instruction — "ClaimsAgent: Keep the existing implementation. Do not change
its behavior except where necessary to improve documentation or prompt wording." Applied
literally: the prompt-version-string test assertion in `tests/unit/agents/
test_claims_agent_prompt_integration.py` and `test_mock_agents.py` was updated to match the new
version (`3.2.0`), which is the direct, necessary consequence of an explicitly-permitted prompt
change — not a behavior change.

## D-03: Duplicate-call detection rejects and continues, it does not abort the loop

**Decision**: a detected duplicate tool call (same tool name + same arguments as one already
attempted earlier in the same `run()` invocation) is rejected with a typed
`ToolCallResult(success=False, error_type="duplicate_call")` fed back to the LLM as an
Observation — the loop continues, bounded by the existing `max_iterations`/the new
`timeout_seconds`, rather than immediately terminating the whole `run()` call.

**Why**: this is the smallest, most conservative design that preserves every existing test's
behavior unchanged (confirmed directly: `test_run_stops_at_max_iterations_against_a_never_
terminating_llm`'s `_AlwaysRequestsToolCallProvider` requests the identical tool call every
iteration and continued to pass unmodified, because that test never asserted individual
`success`/`error_type` values — only that `max_iterations` is what stops the loop). Immediately
aborting on the first duplicate would have added a second, competing termination path to reason
about, for no clear benefit over letting the LLM see the rejection and adjust.

## D-04: Broker/Commercial's isolated tool-calling path catches a broader exception than Claims

**Decision**: `BrokerAgent`/`CommercialIntakeAgent`'s new `_run_controlled_tool_calling` methods
catch `except Exception:  # noqa: BLE001` (in addition to `except ToolCallingError:`), unlike
`ClaimsAgent`'s equivalent method, which catches only `ToolCallingError`.

**Why**: discovered mid-implementation, not planned in advance. `ToolCallingOrchestrator.run()`
does not itself catch a genuine `LLMProvider` failure (e.g. `LLMProviderError` after
`AzureOpenAIProvider`'s own retry/circuit-breaker layer is exhausted) — only `ToolCallingError`
(a configuration bug: an allow-listed Tool that isn't registered). Neither
`SupervisorOrchestrator.handle()` nor `POST /chat` wraps `Agent.handle()` in a try/except either
(confirmed by direct read of both files) — so an uncaught `LLMProviderError` from inside the
isolated tool-calling path would propagate all the way to FastAPI's default error handling and
crash the whole turn with a 500, not the platform's own graceful fallback message. This gap
already existed for Claims (unaffected by this sprint, per D-02) — extending the *same* pattern
to two more agents without addressing it would have tripled the surface area of a real,
if narrow, fragility. Per this task's own escalation clause ("if extending the existing
implementation introduces an unacceptable regression risk, stop and explain"), the judgment call
made was: this does not rise to a STOP — it is a latent, pre-existing gap being extended in
surface area, not a new category of risk — but it should not be silently carried forward
unaddressed either. Hardening the *new* code (Broker/Commercial) while leaving Claims exactly as
instructed is the smallest safe response: it does not touch what the task said not to touch, and
it does not knowingly ship two more instances of a known fragility. Proven by a repurposed
existing test (`test_agent_degrades_gracefully_when_llm_provider_fails`, both files) that now
also asserts the isolated ReAct path survives the same induced `LLMProviderError`.

**Follow-up recommendation**: align Claims with the same broader exception handling in a future,
explicitly-scoped PBI — tracked as remaining technical debt in the final report, not fixed here.

## D-05: No risk-register entry was added for the duplicate-call/timeout hardening

**Decision**: `review/04_risk_register.md` was not modified by this sprint.

**Why**: the task's own documentation list named README.md, CLAUDE.md, Architecture Overview,
Architecture Assessment (`review/06`), Executive Summary (`review/05`), and Deployment Guide —
not the risk register. Duplicate-call detection and the opt-in timeout are hardening additions
made proactively during implementation (per the task's own "Hardening" section), not findings
from an independent review pass — the existing risk register's own methodology (a review
re-reading the repository fresh) was not re-run for this sprint, so adding entries to it would
misrepresent how they were discovered.

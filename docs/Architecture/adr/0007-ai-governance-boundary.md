# ADR-0007: AI Governance Boundary — Deterministic Routing, Deterministic Business Actions

## Status

Accepted — retroactively documented 2026-08-10 (PBI-10-02). This principle has governed the
platform since Sprint 01 (`RuleBasedIntentResolver`) and Sprint 02 (`ToolCallingOrchestrator`),
and is stated directly in CLAUDE.md principles #1–#4. This ADR is the first formal record of the
architectural boundary itself — why the LLM is deliberately excluded from routing and business-
action authority, and how the codebase enforces that exclusion structurally rather than by
convention alone.

## Context

CLAUDE.md states four related principles governing how the LLM may participate in this platform:

1. "AI First, not AI Only" — the LLM handles language understanding, classification support,
   reasoning support, and response generation; business rules stay deterministic.
2. "The LLM is not the source of truth" — business facts come from approved Tools/APIs/governed
   data, never from LLM output.
3. "Tool Calling for business action" — every business action uses a deterministic, versioned,
   testable, auditable Tool.
4. "No direct database access from agents" — agents never query/modify databases directly (a
   corollary: neither does the LLM, since agents are the LLM's only path to any system).

This is one of the most consequential architectural decisions in the platform: an insurance
domain has direct financial and legal exposure (claim registration, commission payment requests,
lead preregistration) if a probabilistic model is ever allowed to authorize an action or determine
a business fact on its own.

## Decision

The LLM's role is bounded on two independent axes, each enforced by code structure, not by prompt
instructions alone:

### 1. Intent routing is deterministic — the LLM never decides which Agent handles a request

`RuleBasedIntentResolver` (`src/supervisor/intent.py`) is pure keyword matching against
bilingual (English/es-MX) keyword lists — "No LLM, no embeddings, no AI of any kind," per its own
module docstring. `SupervisorOrchestrator` (`src/supervisor/orchestrator.py`) calls this resolver,
never an LLM, to select which domain Agent (Claims/Broker/Commercial) handles a turn, with an
explicit "stay with the current agent" fallback on an ambiguous/`UNKNOWN` follow-up rather than
asking a model to guess. The `IntentResolver` Protocol (same file) keeps this swappable in
principle — CLAUDE.md's own docstring note ("A future PBI may add an LLM-backed resolver behind
the same IntentResolver Protocol") — but no LLM-backed resolver has been implemented; today's
routing decision is 100% deterministic in every deployed and tested configuration.

### 2. Business actions execute only through deterministic, code-defined Tools

`ToolCallingOrchestrator` (`src/core/tool_calling/orchestrator.py`) is the only path by which an
LLM's output can result in a Tool executing, and it enforces three structural constraints an LLM
cannot override:

- **Schema origin**: `build_tool_definitions` builds every `LLMToolDefinition` from a Tool's own
  registered `input_model.model_json_schema()` (`src/tools/protocol.py`) — the LLM is offered
  only schemas the codebase defines; it can never introduce a new parameter or a new Tool.
- **Allow-list authorization**: `_execute_tool_call` checks `tool_name not in
  context.allowed_tools` before executing anything — each Agent supplies its own fixed allow-list
  (e.g., Claims never receives `create_commission_payment_request`), so an LLM cannot request a
  Tool outside its Agent's permitted scope even if it hallucinates the name; the call is rejected
  as `"unauthorized"`.
- **Unknown-tool rejection**: a hallucinated, never-registered tool name is rejected as
  `"unknown_tool"` before authorization is even checked — distinguishable in audit output from a
  legitimate-but-unauthorized request.
- **No dynamic execution surface**: the orchestrator's own module docstring states the
  constraint directly — "No `eval()`, no dynamic import, no shell/process execution anywhere in
  this module — the only thing ever invoked is `Tool.execute()` through the existing,
  already-audited `ToolExecutor`."

Every Tool itself (`src/services/tools/*`) is deterministic code: fixed input validation, a fixed
call to a synthetic service/dataset, and a fixed, typed output — never an LLM call inside a Tool.
Claims policy validation (`src/agents/claims/workflow.py::_handle_validating_policy`) is a
concrete example: policy status, payment currency, and coverage are established exclusively by
three Tool calls (`policy_lookup`, `payment_status`, `coverage_lookup`); the LLM is never asked
whether a policy is active or a payment is current — that fact comes from the Tool result, and
only from the Tool result.

### 3. RAG citations are attached deterministically, never selected by the LLM

`Grounder.build_response` (`src/rag/grounder.py`) attaches exactly the citation set
`Grounder.ground` already computed deterministically (deduplicated, score-sorted, capped at
`top_k`) — the method's own docstring states the guarantee directly: "the LLM must never invent a
citation... by construction rather than by post-hoc validation." The LLM produces the response
text; it never determines which source is cited or fabricates a reference.

### 4. Business validation belongs to code, not to the model

Field validation (a policy number's format, a required field being present, a status being
"active" vs. not) is implemented in Pydantic models and plain Python conditionals throughout
`src/agents/*/extraction.py` and `src/agents/*/workflow.py` — never delegated to an LLM's
judgment about whether input is valid. The LLM's role in these flows is limited to natural-
language understanding (extracting a candidate value from free text) and response generation
(phrasing the next question or confirmation) — the validation decision itself is deterministic
code every time.

## Why this architecture was selected instead of allowing the LLM direct access to enterprise systems

- **Auditability.** A deterministic Tool call is logged with a fixed name, fixed input schema, and
  a boolean success flag (CLAUDE.md §10) — reconstructing "what happened and why" from an audit
  log is possible. An LLM given direct system access would make the audit trail dependent on
  interpreting free-text reasoning, which CLAUDE.md §10 explicitly forbids storing ("Do not store
  hidden chain-of-thought").
- **Testability.** `ToolCallingOrchestrator`, `RuleBasedIntentResolver`, and every Tool are unit-
  testable with fixed inputs and fixed expected outputs. An LLM-authorized business action would
  require testing against a non-deterministic component for every regression, which is
  fundamentally weaker guarantee than a deterministic contract test.
- **Domain risk.** This platform's business scope (CLAUDE.md §2) explicitly forbids each Agent
  from making the underlying business decision — Claims "must not determine final coverage,
  reject claims, or authorize indemnity"; Broker Services "must not execute payments, approve
  commissions, modify policies"; Commercial Intake "must not quote, underwrite, define premiums."
  Routing an LLM's own judgment directly into any of these systems would violate this constraint
  by construction, regardless of how carefully the prompt is worded — prompts are not a reliable
  enforcement boundary for a financial/legal-exposure decision (CLAUDE.md §9, Prompts: "Do not
  place business rules exclusively in prompts").
- **Human-in-the-loop compatibility.** CLAUDE.md principle #5 requires escalation for sensitive,
  ambiguous, low-confidence, legal, financial, or coverage-related decisions. A deterministic
  routing/execution boundary makes "this decision needs a human" a code-level branch (e.g., a
  low-confidence intent falling through to `FallbackAgent`) rather than something the LLM itself
  would need to self-report reliably.

## Alternatives considered

- **LLM-authorized Tool execution with no allow-list or schema constraint.** Rejected: this is
  exactly the risk `docs/sprint_03/decisions.md` (PBI-03-01) documented directly after a live
  Ollama test showed the model confidently fabricating plausible arguments for fields the user
  never provided — the allow-list and schema-origin constraints in
  `ToolCallingOrchestrator` exist specifically because ungoverned LLM-to-Tool wiring produces
  exactly this failure mode.
- **LLM-based intent classification (embeddings or a classification prompt).** Rejected for the
  current implementation: CLAUDE.md principle #2 and the "AI First, not AI Only" framing favor a
  deterministic routing layer while the platform is still an academic reference architecture: it
  keeps routing behavior fully predictable and testable. The `IntentResolver` Protocol
  deliberately leaves room for a future LLM-backed resolver without an Agent-level rewrite, but
  adopting one is out of scope for this ADR and would need its own risk analysis (confidence
  thresholds, fallback behavior, and CLAUDE.md principle #5 escalation) before being accepted.
- **Allowing the LLM to select/rank RAG citations itself.** Rejected: CLAUDE.md §4.4 ("RAG must
  provide source references") is enforced structurally by `Grounder`, not left to the model's own
  claimed sourcing — the same class of trust-boundary reasoning as the Tool-execution decision
  above.

## Consequences

- Positive: every business action taken by this platform traces to a deterministic, testable,
  auditable code path — the LLM's blast radius on any actual system is zero without an explicit,
  code-defined Tool in the loop.
- Positive: CLAUDE.md's per-Agent "must not" list (§2) is enforced by the allow-list mechanism at
  the framework level, not only by prompt instruction — an Agent literally cannot execute a Tool
  outside its registered allow-list regardless of what the LLM requests.
- Negative / accepted trade-off: routing quality is bounded by keyword coverage, not semantic
  understanding — several real gaps have been found and fixed this way (e.g., PBI-05-01's
  Property-loss keyword gap, `docs/sprint_05/decisions.md`), and a paraphrase the keyword lists
  don't anticipate can still misroute to `FallbackAgent`. This is an accepted, documented
  trade-off for the predictability and auditability this ADR argues for — not treated as a defect
  to silently patch by handing routing to an LLM.
- Negative / accepted trade-off: any Tool a caller genuinely needs must be explicitly built and
  allow-listed before an Agent can use it — there is no "the LLM figures it out" fallback. This is
  the deliberate cost of the auditability and testability gains above.

## Relationship with other ADRs

- [ADR-0006](0006-provider-abstraction-pattern.md) — the `LLMProvider` abstraction this boundary
  constrains is itself swappable (Mock/Azure OpenAI/Ollama); this ADR's governance boundary holds
  regardless of which concrete `LLMProvider` is in use, since the constraint lives in
  `ToolCallingOrchestrator` and `RuleBasedIntentResolver`, not in any provider implementation.
- [ADR-0003](0003-azure-functions-tool-and-workflow-layer.md) — Tool execution's physical
  location (in-process vs. Azure Functions) is orthogonal to this ADR: the allow-list/schema/
  no-dynamic-execution constraints apply identically regardless of where a Tool physically runs.

## Review triggers

- Before implementing an LLM-backed `IntentResolver` — requires its own ADR addressing confidence
  thresholds, fallback/escalation behavior (CLAUDE.md principle #5), and testability strategy.
- Before allowing any Tool's allow-list to be modified at runtime (today it is fixed at Agent
  construction time in `apps/api/src/api/dependencies.py`) — a dynamic allow-list would weaken
  the auditability guarantee this ADR relies on.
- If any future Tool internally calls an LLM (none does today) — would need explicit reasoning
  about whether that Tool remains "deterministic" for this ADR's purposes.

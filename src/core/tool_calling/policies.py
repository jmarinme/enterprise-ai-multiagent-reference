"""Per-Agent Tool Calling allow-lists (PBI-02-04, CLAUDE.md §2's permitted-scope table).

Each tuple names exactly the registered Tool names (src.tools.registry.ToolRegistry) an
Agent's LLM-driven tool calls may ever reach — anything else is rejected by
ToolCallingOrchestrator as unauthorized before ToolExecutor is ever invoked. Only ClaimsAgent
is actually wired to a live ToolCallingOrchestrator this PBI (matching PBI-02-01/02-03's own
"at least one Agent" precedent, see docs/sprint_02/decisions.md) — BROKER_ALLOWED_TOOLS and
COMMERCIAL_ALLOWED_TOOLS are defined and tested now so the full three-Agent policy design is
complete and ready for a future PBI to wire without re-deriving it.
"""

from __future__ import annotations

CLAIMS_ALLOWED_TOOLS: tuple[str, ...] = (
    "policy_lookup",
    "claims_status",
    "payment_status",
    "claim_registration",
    "adjuster_assignment",
)

# "policy status" (CLAUDE.md §2's Broker Services permitted scope) is the same policy_lookup
# Tool ClaimsAgent uses (PolicyLookupTool's result carries a `status` field) — there is no
# separate "policy_status" Tool in the registry.
BROKER_ALLOWED_TOOLS: tuple[str, ...] = (
    "broker_account_lookup",
    "policy_lookup",
    "transaction_status",
    "commission_lookup",
    "commission_payment_request",
)

# No shared lookup tools included: CommercialIntakeAgent's permitted scope (CLAUDE.md §2) never
# queries policy/broker/claims data, so none of the existing lookup Tools are justified here.
COMMERCIAL_ALLOWED_TOOLS: tuple[str, ...] = ("lead_registration",)

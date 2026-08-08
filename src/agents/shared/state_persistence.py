"""Shared per-turn working-state persistence helper for multi-turn Agents.

Extracted from ClaimsAgent (PBI-01-05) and BrokerAgent (PBI-01-06), which had implemented
this exact deserialize-or-fresh-instance pattern twice. Every multi-turn Agent's state model
is a plain Pydantic BaseModel with every field optional/defaulted (so state_type() is always
constructible), serialized into Conversation.metadata / ConversationContext.metadata /
AgentResponse.metadata under an agent-specific key — this is in-progress session state, not
core business truth (CLAUDE.md §4.3).
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, ValidationError

StateT = TypeVar("StateT", bound=BaseModel)

# Every per-agent working-state metadata key currently in use (PBI-05-01) — used only by
# carry_forward_other_agent_state below, so a cross-domain handoff (Claims -> Broker ->
# Commercial) does not silently destroy an in-progress conversation the caller might return to.
# Adding a new multi-turn Agent's state key here is the only change needed for it to also
# survive a handoff to/from any other Agent.
KNOWN_AGENT_STATE_KEYS: tuple[str, ...] = (
    "claimsIntakeState",
    "brokerInquiryState",
    "commercialIntakeState",
)


def load_agent_state(  # noqa: UP047
    metadata: dict[str, str], key: str, state_type: type[StateT]
) -> StateT:
    """Deserialize state_type from metadata[key], or return a fresh state_type() if the key is
    absent or the stored value is corrupt/incompatible. A bad stored snapshot must never crash
    the conversation — it just starts the flow over.

    PEP 695 `def load_agent_state[StateT: BaseModel](...)` syntax is Python 3.12-only and would
    be a SyntaxError under the 3.11.9 interpreter this project's local dev/test environment
    still runs (pre-existing gap, see docs/sprint_00/decisions.md R-01) — same justified
    suppression already used for ToolResult (src/tools/models.py, PBI-01-02)."""
    raw = metadata.get(key)
    if raw is None:
        return state_type()
    try:
        return state_type.model_validate_json(raw)
    except ValidationError:
        return state_type()


def carry_forward_other_agent_state(metadata: dict[str, str], own_key: str) -> dict[str, str]:
    """Every other Agent's own working-state entry already present in metadata, unchanged and
    un-parsed — never own_key itself. src.supervisor.orchestrator.SupervisorOrchestrator persists
    each turn's AgentResponse.metadata as a full replacement of the conversation's stored
    metadata (see ConversationRepository.append_message's own docstring), so without this, a
    domain handoff (PBI-05-01 requirement 5 — "Ahora quiero consultar mis comisiones.") would
    silently discard whichever other Agent's in-progress intake was under way, purely because
    that Agent didn't happen to be the one that answered this particular turn. Each Agent still
    only ever loads and acts on its own key (via load_agent_state above), so a carried-forward
    entry can never drive another Agent's behavior — it is inert baggage until that Agent is
    addressed again."""
    return {
        key: value
        for key, value in metadata.items()
        if key in KNOWN_AGENT_STATE_KEYS and key != own_key
    }

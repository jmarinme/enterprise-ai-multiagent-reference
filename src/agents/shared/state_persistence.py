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

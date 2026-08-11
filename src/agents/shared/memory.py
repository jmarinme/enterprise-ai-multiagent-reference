"""Global, cross-agent conversation memory (PBI-09-01 — Conversation Intelligence &
Multi-domain Orchestration).

Every domain Agent (Claims, Broker Services, Commercial Intake) reads and writes the *same*
structured memory, so a fact learned in one domain (a resolved customer name, a validated
policy number, a broker's id) is never re-asked when the caller switches to a different domain
in the same conversation ("Claims -> Broker commissions -> Claims" must resume Claims exactly
where it left off, and must not re-ask for a policy Claims already validated if Broker needs it
too). This is the "orchestrator must maintain a structured memory" requirement — modeled here as
a plain shared value object rather than Supervisor-owned mutable state, because
Conversation.metadata is strictly dict[str, str] and is replaced (never merged) on every turn
(see src.agents.shared.state_persistence's own docstring) — exactly the same constraint every
per-agent working-state model already lives under. Each Agent must include
GLOBAL_MEMORY_METADATA_KEY in its own AgentResponse.metadata every turn, exactly like
LANGUAGE_METADATA_KEY (src.agents.shared.language) already must be — a value not re-sent every
turn is silently lost on the very next turn.

This memory is deliberately NOT core business truth (CLAUDE.md §4.3): it is a cache of facts
already confirmed by a Tool or already given by the caller, used only to avoid a redundant
question or a redundant Tool call. Every business action still goes through the same approved
Tools it always did (CLAUDE.md §3) — memory only changes *whether* a field still needs asking or
resolving, never *how* it is validated.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

GLOBAL_MEMORY_METADATA_KEY = "globalMemory"


class ConversationMemory(BaseModel):
    """Structured facts shared across every Agent for one conversation. Every field is optional
    — an empty ConversationMemory() is the correct starting point for a brand-new conversation,
    and is silently returned whenever no memory has been stored yet or a stored snapshot is
    corrupt (same fail-safe behavior as src.agents.shared.state_persistence.load_agent_state)."""

    customer_name: str | None = None
    broker_id: str | None = None
    broker_name: str | None = None
    policy_number: str | None = None
    claim_number: str | None = None
    reference_numbers: list[str] = Field(default_factory=list)
    business_name: str | None = None
    incident_date: str | None = None
    incident_type: str | None = None
    location: str | None = None
    coverage: str | None = None
    current_intent: str | None = None
    previous_intent: str | None = None
    conversation_summary: str | None = None


def load_memory(metadata: dict[str, str]) -> ConversationMemory:
    """Deserialize ConversationMemory from metadata[GLOBAL_MEMORY_METADATA_KEY], or return a
    fresh, empty ConversationMemory() if the key is absent or the stored value is corrupt — a
    bad stored snapshot must never crash the conversation, exactly like load_agent_state."""
    raw = metadata.get(GLOBAL_MEMORY_METADATA_KEY)
    if raw is None:
        return ConversationMemory()
    try:
        return ConversationMemory.model_validate_json(raw)
    except ValueError:
        return ConversationMemory()


def update_memory(memory: ConversationMemory, agent_name: str, **facts: object) -> ConversationMemory:
    """Return a new ConversationMemory with any newly-learned `facts` overlaid onto `memory`.
    Never overwrites an already-known value with an empty one (None, "", or []) — a later turn
    that simply didn't mention a field must not erase what an earlier turn already established.
    Also rotates current_intent -> previous_intent whenever the acting agent differs from the
    last one that touched memory, so "previous intent" always reflects genuine intent switching
    (PBI-09-01 requirement 7), not just a repeated turn with the same agent."""
    updates = {key: value for key, value in facts.items() if value not in (None, "", [])}
    merged = memory.model_copy(update=updates)
    if memory.current_intent != agent_name:
        merged = merged.model_copy(
            update={"previous_intent": memory.current_intent, "current_intent": agent_name}
        )
    return merged


def save_memory(memory: ConversationMemory) -> str:
    """Serialize memory for storage under GLOBAL_MEMORY_METADATA_KEY."""
    return memory.model_dump_json()

"""Tests for src.agents.shared.memory (PBI-09-01 — global cross-agent conversation memory)."""

from __future__ import annotations

from src.agents.shared.memory import (
    GLOBAL_MEMORY_METADATA_KEY,
    ConversationMemory,
    load_memory,
    save_memory,
    update_memory,
)


def test_load_memory_returns_empty_when_key_absent() -> None:
    memory = load_memory({})
    assert memory == ConversationMemory()


def test_load_memory_returns_empty_on_corrupt_stored_value() -> None:
    memory = load_memory({GLOBAL_MEMORY_METADATA_KEY: "not valid json"})
    assert memory == ConversationMemory()


def test_save_and_load_round_trip() -> None:
    original = ConversationMemory(customer_name="Ana Torres", policy_number="SYN-POL-1003")
    metadata = {GLOBAL_MEMORY_METADATA_KEY: save_memory(original)}
    assert load_memory(metadata) == original


def test_update_memory_overlays_new_facts() -> None:
    memory = ConversationMemory()
    updated = update_memory(memory, agent_name="ClaimsAgent", policy_number="SYN-POL-0001")
    assert updated.policy_number == "SYN-POL-0001"


def test_update_memory_never_overwrites_a_known_value_with_an_empty_one() -> None:
    memory = ConversationMemory(customer_name="Juan Pérez")
    updated = update_memory(memory, agent_name="ClaimsAgent", customer_name=None)
    assert updated.customer_name == "Juan Pérez"

    updated_again = update_memory(updated, agent_name="ClaimsAgent", customer_name="")
    assert updated_again.customer_name == "Juan Pérez"


def test_update_memory_rotates_current_intent_to_previous_on_a_different_agent() -> None:
    memory = update_memory(ConversationMemory(), agent_name="ClaimsAgent", policy_number="SYN-POL-0001")
    assert memory.current_intent == "ClaimsAgent"
    assert memory.previous_intent is None

    memory = update_memory(memory, agent_name="BrokerAgent", broker_id="SYN-BRK-0001")
    assert memory.current_intent == "BrokerAgent"
    assert memory.previous_intent == "ClaimsAgent"
    # Facts learned by ClaimsAgent must still be there — intent switching never drops memory.
    assert memory.policy_number == "SYN-POL-0001"


def test_update_memory_does_not_rotate_intent_on_the_same_agent_acting_again() -> None:
    memory = update_memory(ConversationMemory(), agent_name="ClaimsAgent", policy_number="SYN-POL-0001")
    memory = update_memory(memory, agent_name="ClaimsAgent", customer_name="Juan Pérez")
    assert memory.current_intent == "ClaimsAgent"
    assert memory.previous_intent is None

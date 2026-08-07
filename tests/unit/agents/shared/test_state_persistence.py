"""Unit tests for the shared load_agent_state helper (extracted from ClaimsAgent/BrokerAgent
in PBI-01-07): fresh instance on absence, deserialization on a valid stored value, and safe
fallback on a corrupt/incompatible stored value.
"""

from pydantic import BaseModel

from src.agents.shared.state_persistence import load_agent_state


class _ExampleState(BaseModel):
    count: int = 0
    label: str | None = None


def test_returns_a_fresh_instance_when_the_key_is_absent() -> None:
    state = load_agent_state({}, "exampleState", _ExampleState)

    assert state == _ExampleState()


def test_deserializes_a_previously_stored_value() -> None:
    stored = _ExampleState(count=3, label="hello")
    metadata = {"exampleState": stored.model_dump_json()}

    state = load_agent_state(metadata, "exampleState", _ExampleState)

    assert state == stored


def test_returns_a_fresh_instance_when_the_stored_value_is_corrupt() -> None:
    metadata = {"exampleState": "not valid json at all"}

    state = load_agent_state(metadata, "exampleState", _ExampleState)

    assert state == _ExampleState()


def test_returns_a_fresh_instance_when_the_stored_value_is_incompatible() -> None:
    metadata = {"exampleState": '{"count": "not-an-int"}'}

    state = load_agent_state(metadata, "exampleState", _ExampleState)

    assert state == _ExampleState()


def test_only_reads_the_requested_key_ignoring_other_agents_state() -> None:
    metadata = {
        "exampleState": _ExampleState(count=1).model_dump_json(),
        "otherAgentState": '{"unrelated": true}',
    }

    state = load_agent_state(metadata, "exampleState", _ExampleState)

    assert state.count == 1

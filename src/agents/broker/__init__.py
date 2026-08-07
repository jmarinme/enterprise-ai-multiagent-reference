"""Deterministic broker-services state machine used by src.agents.broker_agent.BrokerAgent.

Split from the Agent itself (state.py, extraction.py, workflow.py) so the business logic is
independently unit-testable without constructing an Agent, a PromptManager, or an LLMProvider —
mirrors src.agents.claims's structure (see docs/sprint_01/decisions.md for why this is not a
shared base class with src.agents.claims).
"""

from __future__ import annotations

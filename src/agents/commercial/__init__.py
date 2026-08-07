"""Deterministic commercial-intake state machine used by
src.agents.commercial_intake_agent.CommercialIntakeAgent.

Split from the Agent itself (state.py, extraction.py, workflow.py) so the business logic is
independently unit-testable without constructing an Agent, a PromptManager, or an LLMProvider —
mirrors src.agents.claims's and src.agents.broker's structure.
"""

from __future__ import annotations

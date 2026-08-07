"""Deterministic claims-intake state machine used by src.agents.claims_agent.ClaimsAgent.

Split from the Agent itself (state.py, extraction.py, workflow.py) so the business logic is
independently unit-testable without constructing an Agent, a PromptManager, or an LLMProvider.
"""

from __future__ import annotations

"""Agent Protocol and the registry that maps an intent category to a concrete Agent.

This is what lets the Supervisor stay ignorant of every concrete Agent: it only ever calls
AgentRegistry.resolve(intent), never imports ClaimsAgent/BrokerAgent/etc. directly. Adding a
new agent means registering it here at composition time (see apps/api/src/api/dependencies.py)
— no change to the Supervisor, the registry, or any existing agent.
"""

from __future__ import annotations

from typing import Protocol

from src.agents.shared.semantic_models import TurnInterpretation
from src.core.tool_calling.models import ReActEventSink
from src.supervisor.exceptions import AgentNotFoundError
from src.supervisor.models import AgentRequest, AgentResponse, ConversationContext, IntentCategory


class Agent(Protocol):
    """Contract every domain agent (Claims, Broker, Commercial Intake, and any future agent)
    implements. The Supervisor only ever depends on this Protocol, never a concrete class."""

    name: str

    async def handle(
        self,
        request: AgentRequest,
        context: ConversationContext,
        on_react_event: ReActEventSink | None = None,
        turn_interpretation: TurnInterpretation | None = None,
        turn_interpretation_diagnostic: str = "",
    ) -> AgentResponse:
        """on_react_event (PBI-13-01, optional, default None — every prior caller unaffected):
        forwarded into ToolCallingOrchestrator.run() by any Agent that uses controlled Tool
        Calling; ignored by any Agent that does not (e.g. FallbackAgent).

        turn_interpretation / turn_interpretation_diagnostic (PBI-14-04, optional, default
        None/"" — every prior direct caller, e.g. a unit test that calls Agent.handle() without
        a Supervisor in front of it, is unaffected): the ONE per-turn semantic interpretation
        SupervisorOrchestrator already produced (src.supervisor.semantic_routing.resolve_turn)
        before selecting this Agent. A specialist Agent MUST reuse this — never call
        src.agents.shared.semantic_interpreter.interpret_semantics itself when a non-None value
        is supplied. When None (no Supervisor in front, e.g. a direct unit test), a specialist
        Agent degrades to calling interpret_semantics itself, exactly matching PBI-14-03's own
        behavior — this is a backward-compatible resilience path, never a second call for the
        same Supervisor-routed turn."""
        ...


class AgentRegistry(Protocol):
    """Contract for registering and resolving Agents by intent category."""

    def register(self, intent: IntentCategory, agent: Agent) -> None: ...

    def unregister(self, intent: IntentCategory) -> None: ...

    def resolve(self, intent: IntentCategory) -> Agent: ...

    def list(self) -> list[Agent]: ...


class InMemoryAgentRegistry:
    """Dict-backed AgentRegistry. Holds no hardcoded knowledge of any specific agent — every
    entry arrives via register()."""

    def __init__(self) -> None:
        self._agents: dict[IntentCategory, Agent] = {}

    def register(self, intent: IntentCategory, agent: Agent) -> None:
        self._agents[intent] = agent

    def unregister(self, intent: IntentCategory) -> None:
        self._agents.pop(intent, None)

    def resolve(self, intent: IntentCategory) -> Agent:
        agent = self._agents.get(intent)
        if agent is None:
            raise AgentNotFoundError(intent)
        return agent

    def list(self) -> list[Agent]:
        return list(self._agents.values())

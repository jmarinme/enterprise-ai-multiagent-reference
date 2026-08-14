"""PBI-14-03 section 14 regression scenario: the exact live-observed Claims conversation that
motivated this PBI (PBI-14-01's gap analysis). Drives ClaimsAgent end to end with the real
customer-discovery Tools (Juan Pérez -> two synthetic auto policies) and a scripted, per-turn
semantic interpretation (MockLLMProvider.structured_response_sequence) standing in for a real
LLM's structured output.

Proves two headline PBI-14-03 fixes:
1. Multi-field extraction: a rich narrative message that already contains date/location/loss
   type AND an implicit description of what happened must not be re-asked
   "¿Podrías describir brevemente qué sucedió?" — the semantic-fallback merge fills
   loss_description from the same turn's structured interpretation, exactly the PBI-14-01
   defect (deterministic regex extracted the structured facts but the free-text fallback never
   engaged because a structured field also matched in the same message).
2. Shared confirmation understanding: "sip" (not the literal word "sí") is understood as an
   affirmative pre-registration confirmation.
"""

from pathlib import Path

from src.agents.claims_agent import ClaimsAgent
from src.core.tool_calling.orchestrator import ToolCallingOrchestrator
from src.llm.mock_provider import MockLLMProvider
from src.prompts.filesystem_provider import FileSystemPromptProvider
from src.prompts.manager import PromptManager
from src.rag.grounder import Grounder
from src.rag.local_provider import LocalKnowledgeProvider
from src.rag.retriever import KnowledgeRetriever
from src.services.tools.adjuster_assignment_tool import AdjusterAssignmentTool
from src.services.tools.claim_registration_tool import ClaimRegistrationTool
from src.services.tools.coverage_lookup_tool import CoverageLookupTool
from src.services.tools.customer_lookup_tool import CustomerLookupTool
from src.services.tools.payment_status_tool import PaymentStatusTool
from src.services.tools.policy_lookup_tool import PolicyLookupTool
from src.supervisor.models import AgentRequest, ConversationContext
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry

_SCHEMA_NAME = "claims_semantic_interpretation"
_NARRATIVE_MESSAGE = (
    "el día de ayer estaba lloviendo muy fuerte y de repente me chocaron por atrás, esto "
    "fue en la calle chiclayo de la colonia lindavista"
)
_MINIMAL_INTERPRETATION = '{"intent": "claims", "intent_confidence": 0.9}'
_NARRATIVE_INTERPRETATION = (
    '{"intent": "claims", "intent_confidence": 0.9, "entities": '
    '{"loss_description": "Estaba lloviendo fuerte y lo chocaron por atrás."}}'
)


def _build_agent(llm_provider: MockLLMProvider) -> ClaimsAgent:
    tool_registry = InMemoryToolRegistry()
    tool_registry.register(CustomerLookupTool())
    tool_registry.register(PolicyLookupTool())
    tool_registry.register(PaymentStatusTool())
    tool_registry.register(CoverageLookupTool())
    tool_registry.register(ClaimRegistrationTool())
    tool_registry.register(AdjusterAssignmentTool())
    prompt_manager = PromptManager(
        provider=FileSystemPromptProvider(prompts_root=Path("configs/prompts"))
    )
    knowledge_retriever = KnowledgeRetriever(
        provider=LocalKnowledgeProvider(documents_root=Path("configs/knowledge_base"))
    )
    tool_executor = ToolExecutor(tool_registry=tool_registry)
    return ClaimsAgent(
        tool_executor=tool_executor,
        prompt_manager=prompt_manager,
        llm_provider=llm_provider,
        knowledge_retriever=knowledge_retriever,
        grounder=Grounder(),
        tool_calling_orchestrator=ToolCallingOrchestrator(
            tool_registry=tool_registry, tool_executor=tool_executor, llm_provider=llm_provider
        ),
    )


async def _run_conversation(agent: ClaimsAgent, messages: list[str]) -> list[str]:
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")
    responses: list[str] = []
    for message in messages:
        result = await agent.handle(AgentRequest(message=message, user_id="user-1"), context)
        responses.append(result.response)
        context = context.model_copy(update={"metadata": result.metadata})
    return responses


async def test_customer_discovery_narrative_extraction_and_sip_confirmation() -> None:
    llm_provider = MockLLMProvider(
        structured_response_sequence={
            _SCHEMA_NAME: [
                _MINIMAL_INTERPRETATION,  # turn 1: "quiero reportar un siniestro"
                _MINIMAL_INTERPRETATION,  # turn 2: "Juan Pérez"
                _MINIMAL_INTERPRETATION,  # turn 3: "la primera"
                _NARRATIVE_INTERPRETATION,  # turn 4: the rich narrative message
                _MINIMAL_INTERPRETATION,  # turn 5: phone
                _MINIMAL_INTERPRETATION,  # turn 6: "no" (injuries/third parties)
                _MINIMAL_INTERPRETATION,  # turn 7: "sí" (vehicle_drivable)
                _MINIMAL_INTERPRETATION,  # turn 8: "sip" (confirmation)
            ]
        }
    )
    agent = _build_agent(llm_provider)

    responses = await _run_conversation(
        agent,
        [
            "quiero reportar un siniestro",
            "Juan Pérez",
            "la primera",
            _NARRATIVE_MESSAGE,
            "555-123-4567",
            "no",
            "sí",
            "sip",
        ],
    )

    turn2_policy_selection_prompt, turn3_incident_prompt, turn4_response = (
        responses[1],
        responses[2],
        responses[3],
    )
    # Turn 2: customer discovery surfaced both of Juan Pérez's synthetic auto policies.
    assert "Sentra" in turn2_policy_selection_prompt or "Hilux" in turn2_policy_selection_prompt
    # Turn 3: "la primera" resolved to the Sentra policy and moved on to the combined
    # incident-details question (never a "policy not understood" retry).
    assert "no logré identificar" not in turn3_incident_prompt.lower()
    # Turn 4 (the critical regression assertion): the narrative message already answered
    # date/location/loss-type AND (via the scripted semantic interpretation) the description —
    # the response must move straight to the next genuinely missing field (phone), never
    # re-ask "¿Podrías describir brevemente qué sucedió?".
    assert "describir" not in turn4_response.lower()

    final = responses[-1]
    assert "registrado" in final.lower()
    assert "SYN-CLM-" in final

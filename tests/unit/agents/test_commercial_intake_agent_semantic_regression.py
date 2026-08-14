"""PBI-14-03 section 16 regression scenario: "quiero asegurar una fábrica en Monterrey por 20
millones contra incendio" — a compound new-commercial-insurance-request message. Proves:
1. Multi-field extraction: industry/location/insured_value/insurance_need all resolve from one
   message (via the shared semantic interpretation — none of these has a deterministic keyword
   match for this exact phrasing), so none of those questions is asked again later.
2. Qualification-only framing: the response never quotes a price or implies underwriting.
3. Explicit confirmation before registration (section 11): the lead is registered only after an
   explicit "sí", never automatically once the last field is filled.
"""

from pathlib import Path

from src.agents.commercial_intake_agent import CommercialIntakeAgent
from src.core.tool_calling.orchestrator import ToolCallingOrchestrator
from src.llm.mock_provider import MockLLMProvider
from src.prompts.filesystem_provider import FileSystemPromptProvider
from src.prompts.manager import PromptManager
from src.services.tools.lead_registration_tool import LeadRegistrationTool
from src.supervisor.models import AgentRequest, ConversationContext
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry

_SCHEMA_NAME = "commercial_semantic_interpretation"
_MINIMAL_INTERPRETATION = '{"intent": "commercial", "intent_confidence": 0.9}'
_FACTORY_MESSAGE_INTERPRETATION = (
    '{"intent": "commercial", "intent_confidence": 0.9, "entities": '
    '{"industry": "manufacturing", "location": "Monterrey", '
    '"insured_value": "20,000,000 MXN", "insurance_need": "commercial property"}}'
)


def _build_agent() -> CommercialIntakeAgent:
    tool_registry = InMemoryToolRegistry()
    tool_registry.register(LeadRegistrationTool())
    tool_executor = ToolExecutor(tool_registry=tool_registry)
    llm_provider = MockLLMProvider(
        structured_response_sequence={
            _SCHEMA_NAME: [
                _FACTORY_MESSAGE_INTERPRETATION,  # turn 1: the compound factory/peril message
                _MINIMAL_INTERPRETATION,  # turn 2: company name
                _MINIMAL_INTERPRETATION,  # turn 3: contact name
                _MINIMAL_INTERPRETATION,  # turn 4: preferred channel
                _MINIMAL_INTERPRETATION,  # turn 5: email
                _MINIMAL_INTERPRETATION,  # turn 6: risk description
                _MINIMAL_INTERPRETATION,  # turn 7: confirmation
            ]
        }
    )
    prompt_manager = PromptManager(
        provider=FileSystemPromptProvider(prompts_root=Path("configs/prompts"))
    )
    return CommercialIntakeAgent(
        tool_executor=tool_executor,
        prompt_manager=prompt_manager,
        llm_provider=llm_provider,
        tool_calling_orchestrator=ToolCallingOrchestrator(
            tool_registry=tool_registry, tool_executor=tool_executor, llm_provider=llm_provider
        ),
    )


async def _run_conversation(agent: CommercialIntakeAgent, messages: list[str]) -> list[str]:
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")
    responses: list[str] = []
    for message in messages:
        result = await agent.handle(AgentRequest(message=message, user_id="user-1"), context)
        responses.append(result.response)
        context = context.model_copy(update={"metadata": result.metadata})
    return responses


async def test_compound_factory_peril_message_and_explicit_confirmation() -> None:
    agent = _build_agent()

    responses = await _run_conversation(
        agent,
        [
            "quiero asegurar una fábrica en Monterrey por 20 millones contra incendio",
            "Fábrica Monterrey SA de CV",
            "María López",
            "correo por favor",
            "maria@fabricamty.com",
            "Fabricamos autopartes; la planta principal está en la zona industrial.",
            "sí",
        ],
    )

    # No question ever asks again for the insurance need — it (and industry/location/insured
    # value) resolved from the very first, compound message via the semantic layer.
    for question in responses[1:-1]:
        assert "tipo de seguro o cobertura" not in question.lower()

    # The pre-registration confirmation summary surfaces the qualification-only context the
    # caller volunteered up front, so they can correct it — proving it was genuinely retained
    # from turn 1, not silently dropped.
    pre_confirmation = responses[-2].lower()
    assert "monterrey" in pre_confirmation
    assert "20,000,000" in pre_confirmation

    # Never quotes a price or implies an underwriting/acceptance decision (CLAUDE.md §2).
    combined = " ".join(responses).lower()
    for forbidden in ("cotización", "prima", "quote", "premium", "aprobad", "approved"):
        assert forbidden not in combined

    # The second-to-last response (before the final "sí") is the confirmation summary, not an
    # automatic registration — the lead is registered only on the NEXT (explicitly confirmed)
    # turn.
    assert "confirmas" in pre_confirmation or "sí/no" in pre_confirmation
    assert "SYN-LEAD-" not in responses[-2]

    final = responses[-1]
    assert "SYN-LEAD-" in final
    assert "registrada" in final.lower()

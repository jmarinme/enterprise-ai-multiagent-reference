"""Functional, multi-turn tests for CommercialIntakeAgent (PBI-01-07): the full lead-intake
flow end to end, driven directly against the Agent (mirroring what SupervisorOrchestrator
does). All Tools, the Prompt framework, and MockLLMProvider are real, wired dependencies
except where a stub Prompt/LLM provider is used to prove graceful degradation on failure.
"""

import re
from pathlib import Path

from src.agents.commercial_intake_agent import CommercialIntakeAgent
from src.core.tool_calling.orchestrator import ToolCallingOrchestrator
from src.llm.exceptions import LLMProviderError
from src.llm.mock_provider import MockLLMProvider
from src.llm.models import LLMRequest, LLMResponse
from src.prompts.exceptions import PromptNotFoundError
from src.prompts.filesystem_provider import FileSystemPromptProvider
from src.prompts.manager import PromptManager
from src.prompts.models import PromptRenderContext, RenderedPrompt
from src.services.tools.lead_registration_tool import LeadRegistrationTool
from src.supervisor.models import AgentRequest, ConversationContext
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry

_LEAD_REFERENCE_PATTERN = re.compile(r"SYN-LEAD-\d{4}-\d{4}")


def _build_prompt_manager() -> PromptManager:
    return PromptManager(provider=FileSystemPromptProvider(prompts_root=Path("configs/prompts")))


def _build_agent() -> CommercialIntakeAgent:
    tool_registry = InMemoryToolRegistry()
    tool_registry.register(LeadRegistrationTool())
    tool_executor = ToolExecutor(tool_registry=tool_registry)
    llm_provider = MockLLMProvider()
    return CommercialIntakeAgent(
        tool_executor=tool_executor,
        prompt_manager=_build_prompt_manager(),
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


async def test_full_lead_intake_flow_from_first_contact_to_registration() -> None:
    responses = await _run_conversation(
        _build_agent(),
        [
            "I'd like a quote for new business coverage",
            "Acme Consulting LLC",
            "Jane Doe",
            "email please",
            "jane@example.com",
            "general liability",
            "We provide small business consulting services.",
            # PBI-14-03 section 11: explicit pre-registration confirmation is now required.
            "yes",
        ],
    )

    for question in responses[:-1]:
        assert question.count("?") <= 1

    final = responses[-1]
    assert _LEAD_REFERENCE_PATTERN.search(final)
    assert "registered" in final.lower()


async def test_missing_insurance_need_is_asked_for_specifically() -> None:
    responses = await _run_conversation(
        _build_agent(),
        [
            "I'd like a quote for new business coverage",
            "Acme Consulting LLC",
            "Jane Doe",
            "email please",
            "jane@example.com",
        ],
    )

    assert "insurance" in responses[-1].lower() or "coverage" in responses[-1].lower()


async def test_re_sending_a_message_after_registration_does_not_duplicate_it() -> None:
    agent = _build_agent()
    responses = await _run_conversation(
        agent,
        [
            "I'd like a quote for new business coverage",
            "Acme Consulting LLC",
            "Jane Doe",
            "email please",
            "jane@example.com",
            "general liability",
            "We provide small business consulting services.",
            "yes",
            "thank you!",
        ],
    )

    first_reference = _LEAD_REFERENCE_PATTERN.search(responses[-2])
    second_reference = _LEAD_REFERENCE_PATTERN.search(responses[-1])
    assert first_reference is not None
    assert second_reference is not None
    assert first_reference.group(0) == second_reference.group(0)


async def test_agent_degrades_gracefully_when_lead_registration_tool_is_not_registered() -> None:
    empty_registry = InMemoryToolRegistry()
    empty_tool_executor = ToolExecutor(tool_registry=empty_registry)
    empty_llm_provider = MockLLMProvider()
    agent = CommercialIntakeAgent(
        tool_executor=empty_tool_executor,
        prompt_manager=_build_prompt_manager(),
        llm_provider=empty_llm_provider,
        tool_calling_orchestrator=ToolCallingOrchestrator(
            tool_registry=empty_registry,
            tool_executor=empty_tool_executor,
            llm_provider=empty_llm_provider,
        ),
    )

    responses = await _run_conversation(
        agent,
        [
            "I'd like a quote for new business coverage",
            "Acme Consulting LLC",
            "Jane Doe",
            "email please",
            "jane@example.com",
            "general liability",
            "We provide small business consulting services.",
            "yes",
        ],
    )

    assert "unable to register" in responses[-1].lower()
    assert "traceback" not in responses[-1].lower()
    assert "exception" not in responses[-1].lower()


class _RaisingPromptManager:
    async def render(self, identifier: str, context: PromptRenderContext) -> RenderedPrompt:
        raise PromptNotFoundError(identifier)


class _RaisingLLMProvider:
    async def generate(self, request: LLMRequest) -> LLMResponse:
        raise LLMProviderError("stub", "simulated outage")


async def test_agent_degrades_gracefully_when_prompt_manager_fails() -> None:
    tool_registry = InMemoryToolRegistry()
    tool_registry.register(LeadRegistrationTool())
    tool_executor = ToolExecutor(tool_registry=tool_registry)
    llm_provider = MockLLMProvider()
    agent = CommercialIntakeAgent(
        tool_executor=tool_executor,
        prompt_manager=_RaisingPromptManager(),  # type: ignore[arg-type]
        llm_provider=llm_provider,
        tool_calling_orchestrator=ToolCallingOrchestrator(
            tool_registry=tool_registry, tool_executor=tool_executor, llm_provider=llm_provider
        ),
    )
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    response = await agent.handle(
        AgentRequest(message="I'd like a quote for new business coverage", user_id="user-1"),
        context,
    )

    assert "company" in response.response.lower()
    assert "[prompt=" not in response.response


async def test_agent_degrades_gracefully_when_llm_provider_fails() -> None:
    tool_registry = InMemoryToolRegistry()
    tool_registry.register(LeadRegistrationTool())
    raising_llm_provider = _RaisingLLMProvider()
    agent = CommercialIntakeAgent(
        tool_executor=ToolExecutor(tool_registry=tool_registry),
        prompt_manager=_build_prompt_manager(),
        llm_provider=raising_llm_provider,
        # Proves the PBI-12-04 hardening (broad `except Exception` around the isolated
        # tool-calling path, see commercial_intake_agent.py): a genuine LLMProvider failure —
        # not just a ToolCallingError — inside _run_controlled_tool_calling must also degrade
        # gracefully, not propagate past this Agent and crash the whole turn.
        tool_calling_orchestrator=ToolCallingOrchestrator(
            tool_registry=tool_registry,
            tool_executor=ToolExecutor(tool_registry=tool_registry),
            llm_provider=raising_llm_provider,
        ),
    )
    context = ConversationContext(conversation_id="conv-1", user_id="user-1")

    response = await agent.handle(
        AgentRequest(message="I'd like a quote for new business coverage", user_id="user-1"),
        context,
    )

    assert "company" in response.response.lower()
    assert "[prompt=commercial.system@2.2.0]" in response.metadata["diagnostics"]
    assert "[llm=" not in response.metadata["diagnostics"]

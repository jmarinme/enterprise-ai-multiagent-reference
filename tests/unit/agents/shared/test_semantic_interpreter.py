"""Unit tests for the shared semantic-interpretation helper (PBI-14-03): the ONE per-turn LLM
call repurposed from src.agents.shared.annotation.annotate_with_prompt_and_llm to return a real
structured SemanticInterpretation instead of a discarded completion. Success, and graceful
degradation on Prompt/LLM/parse failure — mirroring test_annotation.py's own coverage for the
call it replaces.
"""

from pathlib import Path

from src.agents.shared.semantic_interpreter import interpret_semantics
from src.agents.shared.semantic_models import ClaimsSemanticInterpretation
from src.llm.exceptions import LLMProviderError
from src.llm.mock_provider import MockLLMProvider
from src.llm.models import LLMGenerationSettings, LLMRequest, LLMResponse, LLMUsage
from src.prompts.exceptions import PromptNotFoundError
from src.prompts.filesystem_provider import FileSystemPromptProvider
from src.prompts.manager import PromptManager
from src.prompts.models import PromptRenderContext, RenderedPrompt

_SCHEMA_NAME = "claims_semantic_interpretation"


def _build_prompt_manager() -> PromptManager:
    return PromptManager(provider=FileSystemPromptProvider(prompts_root=Path("configs/prompts")))


class _RaisingPromptManager:
    async def render(self, identifier: str, context: PromptRenderContext) -> RenderedPrompt:
        raise PromptNotFoundError(identifier)


class _RaisingLLMProvider:
    async def generate(self, request: LLMRequest) -> LLMResponse:
        raise LLMProviderError("stub", "simulated outage")


class _RecordingLLMProvider:
    """Captures every LLMRequest it receives so a test can assert on what interpret_semantics
    actually sent — e.g. the generation settings — without needing a real/mock provider that
    only echoes back derived text."""

    def __init__(self) -> None:
        self.received_requests: list[LLMRequest] = []

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.received_requests.append(request)
        return LLMResponse(
            text='{"intent": "claims", "intent_confidence": 0.9, "entities": {}}',
            model="mock-llm",
            usage=LLMUsage(),
            correlation_id=request.correlation_id,
        )


async def test_returns_the_parsed_structured_interpretation_on_success() -> None:
    llm_provider = MockLLMProvider(
        structured_response_plan={
            _SCHEMA_NAME: (
                '{"intent": "claims", "intent_confidence": 0.92, '
                '"entities": {"loss_type": "collision"}, "confirmation": true}'
            )
        }
    )

    interpretation, diagnostic = await interpret_semantics(
        schema_name=_SCHEMA_NAME,
        schema_type=ClaimsSemanticInterpretation,
        prompt_identifier="claims.system",
        prompt_manager=_build_prompt_manager(),
        llm_provider=llm_provider,
        render_context=PromptRenderContext(agent_name="TestAgent"),
        user_message="tuve un choque",
        correlation_id=None,
        conversation_id="conv-1",
        user_id="user-1",
    )

    assert interpretation.intent == "claims"
    assert interpretation.intent_confidence == 0.92
    assert interpretation.entities.loss_type == "collision"
    assert interpretation.confirmation is True
    assert diagnostic.startswith("[prompt=claims.system@")
    assert "[llm=mock-llm]" in diagnostic


async def test_degrades_to_a_safe_empty_interpretation_when_prompt_manager_fails() -> None:
    interpretation, diagnostic = await interpret_semantics(
        schema_name=_SCHEMA_NAME,
        schema_type=ClaimsSemanticInterpretation,
        prompt_identifier="claims.system",
        prompt_manager=_RaisingPromptManager(),  # type: ignore[arg-type]
        llm_provider=MockLLMProvider(),
        render_context=PromptRenderContext(agent_name="TestAgent"),
        user_message="hello",
        correlation_id=None,
        conversation_id="conv-1",
        user_id="user-1",
    )

    assert interpretation.intent == "unknown"
    assert interpretation.intent_confidence == 0.0
    assert diagnostic == ""


async def test_degrades_to_a_safe_empty_interpretation_when_llm_provider_fails() -> None:
    interpretation, diagnostic = await interpret_semantics(
        schema_name=_SCHEMA_NAME,
        schema_type=ClaimsSemanticInterpretation,
        prompt_identifier="claims.system",
        prompt_manager=_build_prompt_manager(),
        llm_provider=_RaisingLLMProvider(),
        render_context=PromptRenderContext(agent_name="TestAgent"),
        user_message="hello",
        correlation_id=None,
        conversation_id="conv-1",
        user_id="user-1",
    )

    assert interpretation.intent == "unknown"
    assert interpretation.intent_confidence == 0.0
    assert "[prompt=claims.system@" in diagnostic
    assert "[llm=" not in diagnostic


async def test_degrades_to_a_safe_empty_interpretation_on_malformed_json() -> None:
    llm_provider = MockLLMProvider(
        structured_response_plan={_SCHEMA_NAME: "this is not valid JSON"}
    )

    interpretation, diagnostic = await interpret_semantics(
        schema_name=_SCHEMA_NAME,
        schema_type=ClaimsSemanticInterpretation,
        prompt_identifier="claims.system",
        prompt_manager=_build_prompt_manager(),
        llm_provider=llm_provider,
        render_context=PromptRenderContext(agent_name="TestAgent"),
        user_message="hello",
        correlation_id=None,
        conversation_id="conv-1",
        user_id="user-1",
    )

    assert interpretation.intent == "unknown"
    assert interpretation.intent_confidence == 0.0
    assert "[llm=mock-llm]" in diagnostic


async def test_never_exposes_a_chain_of_thought_or_reasoning_field() -> None:
    """CLAUDE.md §10 / PBI-14-03 section 3: the schema itself must have no such field at all."""
    schema = ClaimsSemanticInterpretation.model_json_schema()

    forbidden_terms = ("reasoning", "chain_of_thought", "thought", "rationale")
    property_names = {name.lower() for name in schema.get("properties", {})}
    assert not (property_names & set(forbidden_terms))


async def test_semantic_call_uses_a_larger_token_budget_than_the_global_default() -> None:
    """PBI-14-13: gpt-5-mini (a reasoning-family model) spends tokens from this SAME budget on
    hidden reasoning before any visible output — the shared 512-token default left
    message.content empty for a live DEV TurnInterpretation call (correlationId
    55c38af7-c8c1-4e87-a3f4-5e65b0a2f91d), which model_validate_json("") correctly rejected as
    invalid JSON. interpret_semantics must request a larger, explicit budget on every call."""
    recording_provider = _RecordingLLMProvider()

    await interpret_semantics(
        schema_name=_SCHEMA_NAME,
        schema_type=ClaimsSemanticInterpretation,
        prompt_identifier="claims.system",
        prompt_manager=_build_prompt_manager(),
        llm_provider=recording_provider,
        render_context=PromptRenderContext(agent_name="TestAgent"),
        user_message="tuve un choque",
        correlation_id=None,
        conversation_id="conv-1",
        user_id="user-1",
    )

    assert len(recording_provider.received_requests) == 1
    sent_settings = recording_provider.received_requests[0].settings
    assert sent_settings.max_output_tokens == 4096
    assert sent_settings.max_output_tokens > LLMGenerationSettings().max_output_tokens


def test_global_llm_generation_settings_default_is_unchanged() -> None:
    """Proves the fix is scoped to interpret_semantics only — LLMGenerationSettings' own shared
    default (what ToolCallingOrchestrator/annotate_with_prompt_and_llm still use for every
    non-semantic-interpretation call) must remain exactly what it was before this PBI."""
    assert LLMGenerationSettings().max_output_tokens == 512


async def test_semantic_call_preserves_every_other_generation_setting() -> None:
    """Only max_output_tokens changes — temperature/timeout_seconds/model stay at
    LLMGenerationSettings' own defaults, never overridden by this fix."""
    recording_provider = _RecordingLLMProvider()

    await interpret_semantics(
        schema_name=_SCHEMA_NAME,
        schema_type=ClaimsSemanticInterpretation,
        prompt_identifier="claims.system",
        prompt_manager=_build_prompt_manager(),
        llm_provider=recording_provider,
        render_context=PromptRenderContext(agent_name="TestAgent"),
        user_message="tuve un choque",
        correlation_id=None,
        conversation_id="conv-1",
        user_id="user-1",
    )

    sent_settings = recording_provider.received_requests[0].settings
    default_settings = LLMGenerationSettings()
    assert sent_settings.temperature == default_settings.temperature
    assert sent_settings.timeout_seconds == default_settings.timeout_seconds
    assert sent_settings.model == default_settings.model

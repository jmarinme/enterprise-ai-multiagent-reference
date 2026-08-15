"""Integration tests for the structured routing-decision/fallback log events emitted by
apps/api/src/api/routes/chat.py (PBI-14-07).

Drives the real post_chat() route handler directly (bypassing FastAPI's HTTP/DI layer, which
tests/unit/api/test_chat_correlation_id_observability.py already exercises for the correlation
id itself) with a real SupervisorOrchestrator, real src.supervisor.semantic_routing.resolve_turn,
and a scripted MockLLMProvider — only the log CAPTURE is test infrastructure. Asserts the actual
JSON a real logging.Formatter (observability.logging.JsonFormatter) would produce, not just the
raw LogRecord, so a regression in the formatter's allowlist would also be caught here.
"""

import json
import logging
from pathlib import Path

import pytest
from api.auth.models import AuthenticatedUser
from api.routes.chat import ChatRequest, post_chat
from observability.logging import JsonFormatter, correlation_id_ctx_var

from src.agents.fallback_agent import FallbackAgent
from src.llm.exceptions import LLMProviderError
from src.llm.mock_provider import MockLLMProvider
from src.llm.models import LLMRequest, LLMResponse
from src.observability.pricing import PricingCatalog
from src.observability.service import ObservabilityService
from src.prompts.filesystem_provider import FileSystemPromptProvider
from src.prompts.manager import PromptManager
from src.services.conversation_store.in_memory import InMemoryConversationRepository
from src.services.observability_store.in_memory import InMemoryObservabilityRepository
from src.supervisor.intent import RuleBasedIntentResolver
from src.supervisor.models import AgentResponse, IntentCategory
from src.supervisor.orchestrator import SupervisorOrchestrator
from src.supervisor.registry import InMemoryAgentRegistry

_SCHEMA_NAME = "turn_interpretation"
_LOGGER_NAME = "api.routes.chat"


class _StubClaimsAgent:
    """A minimal Agent double — real ClaimsAgent needs a full tool registry this test doesn't
    need, since it only asserts what chat.py logs about the ROUTING decision, never business
    behavior."""

    name = "ClaimsAgent"

    async def handle(self, request, context, on_react_event=None, turn_interpretation=None,
                      turn_interpretation_diagnostic="") -> AgentResponse:
        return AgentResponse(
            conversation_id=context.conversation_id,
            agent=self.name,
            intent=IntentCategory.CLAIMS,
            response="stub claims response",
        )


class _FakeRequestState:
    def __init__(self, correlation_id: str) -> None:
        self.correlation_id = correlation_id


class _FakeHttpRequest:
    def __init__(self, correlation_id: str) -> None:
        self.state = _FakeRequestState(correlation_id)


class _RaisingLLMProvider:
    """Simulates a genuine Azure OpenAI outage for the semantic call."""

    async def generate(self, request: LLMRequest) -> LLMResponse:
        raise LLMProviderError("azure_openai", "simulated outage")

    async def health_check(self) -> bool:
        return False


def _build_prompt_manager() -> PromptManager:
    return PromptManager(provider=FileSystemPromptProvider(prompts_root=Path("configs/prompts")))


def _build_supervisor(llm_provider) -> SupervisorOrchestrator:
    registry = InMemoryAgentRegistry()
    registry.register(IntentCategory.CLAIMS, _StubClaimsAgent())
    registry.register(IntentCategory.UNKNOWN, FallbackAgent())
    return SupervisorOrchestrator(
        conversation_repository=InMemoryConversationRepository(),
        intent_resolver=RuleBasedIntentResolver(),
        agent_registry=registry,
        prompt_manager=_build_prompt_manager(),
        llm_provider=llm_provider,
    )


@pytest.fixture
def observability_service(tmp_path) -> ObservabilityService:
    catalog_path = tmp_path / "pricing.json"
    catalog_path.write_text('{"catalogVersion": "test", "entries": []}', encoding="utf-8")
    return ObservabilityService(
        repository=InMemoryObservabilityRepository(),
        pricing_catalog=PricingCatalog(catalog_path),
    )


def _turn_json(intent: str, confidence: float, *, requires_clarification: bool = False) -> str:
    return (
        f'{{"intent": "{intent}", "intent_confidence": {confidence}, '
        f'"requires_clarification": {"true" if requires_clarification else "false"}}}'
    )


async def _run_post_chat(
    message: str, llm_provider, observability_service, caplog
) -> tuple[dict, dict]:
    """Returns (chat_response_as_dict, the semantic_routing_* log event as a real
    JsonFormatter-serialized dict)."""
    supervisor = _build_supervisor(llm_provider)
    caplog.set_level(logging.INFO, logger=_LOGGER_NAME)

    # CorrelationIdMiddleware (apps/api/src/api/middleware/correlation_id.py) normally sets this
    # contextvar before post_chat() runs — calling post_chat() directly (bypassing the HTTP/DI
    # layer, see module docstring) means this test must set it itself to faithfully reproduce
    # what a real request does.
    token = correlation_id_ctx_var.set("test-correlation-id")
    try:
        response = await post_chat(
            chat_request=ChatRequest(message=message),
            http_request=_FakeHttpRequest(correlation_id="test-correlation-id"),
            current_user=AuthenticatedUser(
                user_id="test-user-1",
                oid="00000000-0000-0000-0000-000000000001",
                tid="11111111-1111-1111-1111-111111111111",
                name="Test User",
                email=None,
            ),
            supervisor=supervisor,
            observability=observability_service,
        )
    finally:
        correlation_id_ctx_var.reset(token)

    formatter = JsonFormatter()
    routing_records = [
        r
        for r in caplog.records
        if r.name == _LOGGER_NAME and getattr(r, "event", "").startswith("semantic_routing_")
    ]
    assert len(routing_records) == 1, (
        f"expected exactly one semantic_routing_* log event, got {len(routing_records)}"
    )
    logged = json.loads(formatter.format(routing_records[0]))
    return response.model_dump(), logged


async def test_successful_semantic_routing_emits_decision_event(
    observability_service, caplog
) -> None:
    llm_provider = MockLLMProvider(
        structured_response_plan={_SCHEMA_NAME: _turn_json("claims", 0.91)}
    )

    _, logged = await _run_post_chat(
        "un camión me pegó por atrás", llm_provider, observability_service, caplog
    )

    assert logged["event"] == "semantic_routing_decision"
    assert logged["semanticCallAttempted"] is True
    assert logged["semanticCallSucceeded"] is True
    assert logged["detectedIntent"] == "CLAIMS"
    assert logged["intentConfidence"] == 0.91
    assert logged["routingSource"] == "semantic"
    assert logged["selectedAgent"] == "ClaimsAgent"
    assert logged["requiresClarification"] is False
    assert logged["semanticErrorCategory"] is None
    assert logged["correlationId"] == "test-correlation-id"
    assert isinstance(logged["runId"], str) and logged["runId"]
    assert isinstance(logged["messageId"], str) and logged["messageId"]
    assert isinstance(logged["conversationId"], str) and logged["conversationId"]
    assert isinstance(logged["durationMs"], float)


async def test_ambiguous_semantic_routing_emits_decision_event_with_clarification(
    observability_service, caplog
) -> None:
    llm_provider = MockLLMProvider(
        structured_response_plan={
            _SCHEMA_NAME: _turn_json("claims", 0.6, requires_clarification=True)
        }
    )

    _, logged = await _run_post_chat(
        "quiero revisar lo de mi negocio", llm_provider, observability_service, caplog
    )

    # Ambiguity is distinguishable from a technical failure: still "_decision" (the semantic
    # call succeeded), never "_fallback".
    assert logged["event"] == "semantic_routing_decision"
    assert logged["semanticCallSucceeded"] is True
    assert logged["requiresClarification"] is True
    assert logged["routingSource"] == "clarification"
    assert logged["semanticErrorCategory"] is None


async def test_semantic_service_failure_emits_fallback_event(
    observability_service, caplog
) -> None:
    _, logged = await _run_post_chat(
        "I need to file a claim", _RaisingLLMProvider(), observability_service, caplog
    )

    assert logged["event"] == "semantic_routing_fallback"
    assert logged["semanticCallAttempted"] is True
    assert logged["semanticCallSucceeded"] is False
    assert logged["routingSource"] == "deterministic_fallback"
    assert logged["semanticErrorCategory"] == "provider_error"


async def test_unknown_intent_emits_decision_event_with_fallback_agent(
    observability_service, caplog
) -> None:
    llm_provider = MockLLMProvider(
        structured_response_plan={_SCHEMA_NAME: _turn_json("unknown", 0.9)}
    )

    _, logged = await _run_post_chat(
        "cuéntame un chiste", llm_provider, observability_service, caplog
    )

    # Unknown/out-of-scope is a real, successful classification, not a technical failure.
    assert logged["event"] == "semantic_routing_decision"
    assert logged["semanticCallSucceeded"] is True
    assert logged["detectedIntent"] == "UNKNOWN"
    assert logged["selectedAgent"] == "FallbackAgent"
    assert logged["semanticErrorCategory"] is None


async def test_routing_log_event_never_contains_the_raw_user_message(
    observability_service, caplog
) -> None:
    secret_message = "quiero reportar un percance derivado de la fuerte lluvia UNIQUE_MARKER_XYZ"  # pragma: allowlist secret -- variable name only; value is a synthetic test sentence
    llm_provider = MockLLMProvider(
        structured_response_plan={_SCHEMA_NAME: _turn_json("claims", 0.91)}
    )

    _, logged = await _run_post_chat(
        secret_message, llm_provider, observability_service, caplog
    )

    serialized = json.dumps(logged)
    assert "UNIQUE_MARKER_XYZ" not in serialized

"""Unit tests for LLM request/response contracts and generation settings validation."""

import pytest
from pydantic import ValidationError

from src.llm.models import (
    LLMGenerationSettings,
    LLMMessage,
    LLMMessageRole,
    LLMRequest,
    LLMResponse,
    LLMUsage,
)


def test_generation_settings_defaults_are_deterministic_friendly() -> None:
    settings = LLMGenerationSettings()

    assert settings.temperature == 0.0
    assert settings.max_output_tokens == 512
    assert settings.timeout_seconds == 30.0
    assert settings.model is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"temperature": -0.1},
        {"temperature": 2.1},
        {"max_output_tokens": 0},
        {"max_output_tokens": -1},
        {"timeout_seconds": 0},
        {"timeout_seconds": -5},
    ],
)
def test_generation_settings_rejects_out_of_range_values(kwargs: dict) -> None:
    with pytest.raises(ValidationError):
        LLMGenerationSettings(**kwargs)


def test_generation_settings_accepts_boundary_values() -> None:
    settings = LLMGenerationSettings(temperature=0.0, max_output_tokens=1, timeout_seconds=0.01)

    assert settings.temperature == 0.0
    assert settings.max_output_tokens == 1


def test_llm_request_carries_messages_and_context_identifiers() -> None:
    request = LLMRequest(
        messages=[LLMMessage(role=LLMMessageRole.USER, content="hello")],
        correlation_id="corr-1",
        conversation_id="conv-1",
        user_id="user-1",
    )

    assert len(request.messages) == 1
    assert request.settings == LLMGenerationSettings()
    assert request.correlation_id == "corr-1"


def test_llm_response_defaults_usage_to_zero() -> None:
    response = LLMResponse(text="hello", model="mock-llm")

    assert response.usage == LLMUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)

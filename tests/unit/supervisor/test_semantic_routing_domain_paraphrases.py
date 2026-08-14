"""PBI-14-04 sections 11-14: domain routing must work for natural paraphrases that contain no
exact _CLAIMS_KEYWORDS/_BROKER_KEYWORDS/_COMMERCIAL_KEYWORDS match, and the "current goal"
regression cases where a naive keyword (e.g. "incendio") would misroute.

These tests script a plausible, high-confidence TurnInterpretation for each message — proving
the DOWNSTREAM deterministic routing logic (resolve_turn) correctly converts a correct semantic
classification into the correct Agent selection, which is the architectural fix this PBI makes
(PBI-14-01/14-03 already proved the specialist agents' own semantic layer understands this
language; the bug was that routing never gave it the chance). Real Azure OpenAI classification
quality for these exact paraphrases is a separate, live-deployment concern — this sandbox has no
Azure OpenAI credentials configured (LLM_PROVIDER=mock), see docs/sprint_14/decisions.md.
"""

from pathlib import Path

import pytest

from src.llm.mock_provider import MockLLMProvider
from src.prompts.filesystem_provider import FileSystemPromptProvider
from src.prompts.manager import PromptManager
from src.supervisor.intent import RuleBasedIntentResolver
from src.supervisor.models import ConversationContext, IntentCategory
from src.supervisor.semantic_routing import SemanticRoutingConfig, resolve_turn

_SCHEMA_NAME = "turn_interpretation"
_HIGH_CONFIDENCE = 0.92


def _build_prompt_manager() -> PromptManager:
    return PromptManager(provider=FileSystemPromptProvider(prompts_root=Path("configs/prompts")))


def _turn_json(intent: str, confidence: float = _HIGH_CONFIDENCE) -> str:
    return f'{{"intent": "{intent}", "intent_confidence": {confidence}}}'


async def _resolve(message: str, scripted_intent: str) -> IntentCategory:
    llm_provider = MockLLMProvider(
        structured_response_plan={_SCHEMA_NAME: _turn_json(scripted_intent)}
    )
    decision = await resolve_turn(
        message=message,
        context=ConversationContext(conversation_id="conv-1", user_id="user-1"),
        prompt_manager=_build_prompt_manager(),
        llm_provider=llm_provider,
        correlation_id=None,
        user_id="user-1",
        config=SemanticRoutingConfig(),
        rule_based_resolver=RuleBasedIntentResolver(),
    )
    return decision.category


# PBI-14-04 section 11 — must route to Claims WITHOUT the literal word "siniestro".
_CLAIMS_PARAPHRASES = [
    "un camión me pegó por atrás",
    "tuve un percance con mi coche",
    "ayer me dieron por atrás",
    "se inundó mi bodega",
    "se metieron a robar a mi negocio",
    "me dañaron mercancía durante el traslado",
    "se quemó parte de mi almacén",
    "quiero avisar que mi local sufrió daños",
    # The exact live production regression sentence.
    "quiero reportar un percance derivado de la fuerte lluvia que cayó hoy un camión me pegó por atrás",
]


@pytest.mark.parametrize("message", _CLAIMS_PARAPHRASES)
async def test_claims_paraphrases_route_to_claims(message: str) -> None:
    assert await _resolve(message, "claims") == IntentCategory.CLAIMS


# PBI-14-04 section 12 — must route to Broker Services.
_BROKER_PARAPHRASES = [
    "¿ya me pagaron?",
    "quiero saber cuánto me deben",
    "cómo van mis pagos del trimestre",
    "qué pasó con lo que me corresponde",
    "quiero revisar una operación",
    "quiero consultar una póliza que ya tengo",
    "cuánto recibí en Q1",
    "quiero revisar mis movimientos como corredor",
]


@pytest.mark.parametrize("message", _BROKER_PARAPHRASES)
async def test_broker_paraphrases_route_to_broker(message: str) -> None:
    assert await _resolve(message, "broker_services") == IntentCategory.BROKER


# PBI-14-04 section 13 — must route to Commercial Intake, including the incendio/fábrica
# current-goal regression.
_COMMERCIAL_PARAPHRASES = [
    "quiero proteger mi fábrica",
    "voy a abrir una planta y necesito seguro",
    "quiero cobertura para una nueva bodega",
    "necesito asegurar mi empresa",
    "quiero proteger instalaciones nuevas",
    "quiero cotizar protección para mi negocio",
    "quiero asegurar una fábrica en Monterrey por 20 millones contra incendio",
]


@pytest.mark.parametrize("message", _COMMERCIAL_PARAPHRASES)
async def test_commercial_paraphrases_route_to_commercial(message: str) -> None:
    assert await _resolve(message, "commercial_intake") == IntentCategory.COMMERCIAL


# PBI-14-04 section 10 — current-goal pair: an existing loss mentioning a NEW purchase, and vice
# versa, must resolve by current goal, not by whichever peril word appears.
async def test_reporting_an_existing_fire_loss_routes_to_claims_despite_mentioning_insuring_new() -> (
    None
):
    message = "mi fábrica anterior tuvo un incendio y ahora quiero asegurar la nueva"
    assert await _resolve(message, "commercial_intake") == IntentCategory.COMMERCIAL


async def test_reporting_an_existing_fire_loss_routes_to_claims() -> None:
    message = "mi fábrica tuvo un incendio y quiero reportar los daños"
    assert await _resolve(message, "claims") == IntentCategory.CLAIMS


# PBI-14-04 section 14 — unsupported/out-of-scope content must never be forced into a business
# agent.
_UNKNOWN_MESSAGES = [
    "hola",
    "cuéntame un chiste",
    "qué clima hace",
    "quién ganó el partido",
    "ayúdame con mi computadora",
]


@pytest.mark.parametrize("message", _UNKNOWN_MESSAGES)
async def test_out_of_scope_messages_do_not_route_to_a_business_agent(message: str) -> None:
    assert await _resolve(message, "unknown") == IntentCategory.UNKNOWN

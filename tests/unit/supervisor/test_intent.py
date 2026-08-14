"""Unit tests for RuleBasedIntentResolver. Purely deterministic keyword matching — no AI."""

import pytest

from src.supervisor.intent import RuleBasedIntentResolver
from src.supervisor.models import IntentCategory


@pytest.mark.parametrize(
    ("message", "expected_category"),
    [
        ("I need to file a claim after an accident", IntentCategory.CLAIMS),
        ("What is the status of my policy with my broker?", IntentCategory.BROKER),
        ("I'd like a quote for new business coverage options", IntentCategory.COMMERCIAL),
        ("Hello, how are you today?", IntentCategory.UNKNOWN),
        # PBI-01-06's own example phrasing — "status of a/my policy" does not contain the
        # literal substring "policy status", so the bare "policy" keyword is required.
        ("I want to know the status of a policy.", IntentCategory.BROKER),
        ("What is the status of my transaction?", IntentCategory.BROKER),
        # PBI-05-01 regression guard: found via live DEV validation — the PBI's own canonical
        # Property-claim example never says "siniestro"/"accidente" at all.
        ("Ayer llovió muy fuerte y se inundó mi casa.", IntentCategory.CLAIMS),
        ("Se inundó mi casa.", IntentCategory.CLAIMS),
        ("Me robaron el auto anoche.", IntentCategory.CLAIMS),
        ("Hubo un incendio en mi negocio.", IntentCategory.CLAIMS),
        # PBI-14-03 section 5 hard regression case: contains "incendio" (a _CLAIMS_KEYWORDS
        # entry) but describes a NEW commercial insurance request against that peril, not a
        # claim being reported — must route to Commercial, never Claims.
        (
            "quiero asegurar una fábrica en Monterrey por 20 millones contra incendio",
            IntentCategory.COMMERCIAL,
        ),
        ("I want to insure our new business against fire damage.", IntentCategory.COMMERCIAL),
        # Spanish policy-status inquiry gap fix (PBI-14-01 finding): no English "policy"
        # keyword and no compound "pago de comisión" phrase.
        ("¿Cuál es el estado de mi póliza?", IntentCategory.BROKER),
        ("Quiero saber el estado de mi pago.", IntentCategory.BROKER),
    ],
)
async def test_resolve_returns_expected_category(
    message: str, expected_category: IntentCategory
) -> None:
    resolver = RuleBasedIntentResolver()

    intent = await resolver.resolve(message)

    assert intent.category == expected_category


async def test_resolve_is_case_insensitive() -> None:
    resolver = RuleBasedIntentResolver()

    intent = await resolver.resolve("I WANT TO REPORT A CLAIM")

    assert intent.category == IntentCategory.CLAIMS


async def test_unknown_intent_has_zero_confidence() -> None:
    resolver = RuleBasedIntentResolver()

    intent = await resolver.resolve("asdkjfh qwoeiru")

    assert intent.category == IntentCategory.UNKNOWN
    assert intent.confidence == 0.0


async def test_matched_intent_has_full_confidence() -> None:
    resolver = RuleBasedIntentResolver()

    intent = await resolver.resolve("claim")

    assert intent.confidence == 1.0

"""Shared conversation-language resolution (PBI-04-04).

Spanish (es-MX) is this platform's default language (CLAUDE.md's Sprint 04 UX mandate: Tokio
Marine Mexico is a Spanish-speaking market). Language is decided deterministically, never by
the LLM (MockLLMProvider is content-agnostic and cannot perform real NLU — same rationale as
every extraction module under src.agents.*.extraction): once resolved for a conversation, it is
stuck to that conversation via ConversationContext.metadata["language"], exactly like each
Agent's own working state, so "if the conversation starts in Spanish, continue in Spanish" (and
symmetrically for English) holds across every turn without re-detecting each time.

Every multi-turn Agent must include LANGUAGE_METADATA_KEY in its own AgentResponse.metadata
alongside its state key — src.supervisor.orchestrator.SupervisorOrchestrator persists
AgentResponse.metadata as a full replacement of the conversation's stored metadata, never a
merge (see ConversationRepository.append_message's own docstring), so a value not re-sent every
turn would be silently lost on the very next turn.
"""

from __future__ import annotations

import re
from typing import Literal

Language = Literal["es-MX", "en"]

LANGUAGE_METADATA_KEY = "language"
DEFAULT_LANGUAGE: Language = "es-MX"

_SPANISH_CHARS = set("áéíóúñ¿¡")

# Deliberately small, high-precision word lists (false negatives just fall through to the
# Spanish-first default, which is always the safe choice for this platform) rather than an
# exhaustive dictionary — same "deterministic, minimal, provably correct" bias as every other
# extraction module in src.agents.*.extraction.
_ENGLISH_SIGNAL_WORDS = {
    "the", "hello", "hi", "claim", "policy", "commission", "quote", "accident", "payment",
    "please", "thanks", "thank", "yes", "help", "need", "want", "my", "report", "check",
    "insurance", "business", "company", "broker", "coverage", "damage", "adjuster",
}
_SPANISH_SIGNAL_WORDS = {
    "hola", "quiero", "necesito", "cuales", "cuáles", "mis", "tuve", "reportar", "siniestro",
    "comision", "comisión", "comisiones", "poliza", "póliza", "cotizacion", "cotización",
    "choque", "empresa", "asegurar", "pago", "gracias", "ayuda", "accidente", "por", "favor",
    "necesita", "quiere",
}

_WORD_PATTERN = re.compile(r"[a-zA-ZñÑáéíóúÁÉÍÓÚ]+")


def detect_language(message: str) -> Language:
    """Deterministic, best-effort language guess for a single message. Defaults to Spanish
    (this platform's default language) unless the message shows a clear, stronger English
    signal — Spanish-leaning or ambiguous messages both resolve to es-MX."""
    lowered = message.lower()
    if any(char in lowered for char in _SPANISH_CHARS):
        return "es-MX"

    words = set(_WORD_PATTERN.findall(lowered))
    spanish_hits = len(words & _SPANISH_SIGNAL_WORDS)
    english_hits = len(words & _ENGLISH_SIGNAL_WORDS)
    if english_hits > spanish_hits:
        return "en"
    return DEFAULT_LANGUAGE


def resolve_language(context_metadata: dict[str, str], message: str) -> Language:
    """The conversation's already-established language (sticky), or a fresh detection for a
    brand-new conversation. Callers must echo the result back into their own
    AgentResponse.metadata[LANGUAGE_METADATA_KEY] every turn — see module docstring."""
    stored = context_metadata.get(LANGUAGE_METADATA_KEY)
    if stored in ("es-MX", "en"):
        return stored  # type: ignore[return-value]
    return detect_language(message)

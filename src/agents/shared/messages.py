"""Tiny bilingual message-catalog helper shared by every multi-turn Agent (PBI-04-04).

Each agent module (claims/broker/commercial) owns its own catalog — a
dict[str, dict[Language, str]] — colocated with the state machine that uses it, exactly like
FIELD_PROMPTS already was before this PBI. This helper only centralizes the lookup-with-
Spanish-fallback mechanics, not the message content itself (CLAUDE.md §7: minimal shared
abstraction, no premature base class).
"""

from __future__ import annotations

from src.agents.shared.language import DEFAULT_LANGUAGE, Language

MessageCatalog = dict[str, dict[Language, str]]


def t(catalog: MessageCatalog, key: str, language: Language, **kwargs: object) -> str:
    """Resolve catalog[key] in `language`, falling back to the default language (es-MX) if a
    translation is missing, then `.format(**kwargs)` if any were given."""
    entry = catalog[key]
    template = entry.get(language) or entry[DEFAULT_LANGUAGE]
    return template.format(**kwargs) if kwargs else template

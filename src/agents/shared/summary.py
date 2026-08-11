"""Shared conversation-progress summary formatting (PBI-09-01 requirement 6 — "after several
turns, summarize what is already known before asking for what's still missing").

Deliberately a pure text-formatting helper, not a source of any business fact: callers decide
which fields count as "known" and their display label (each agent already owns its own
FIELD_PROMPTS-style label catalog, colocated with its own state model — this only centralizes
the checkmark-list layout every Agent uses, exactly like src.agents.shared.messages.t only
centralizes catalog lookup, never the catalog content itself).
"""

from __future__ import annotations

from src.agents.shared.language import Language

_HEADER: dict[Language, str] = {
    "es-MX": "Hasta ahora tengo:",
    "en": "So far I have:",
}
_REMAINING_PREFIX: dict[Language, str] = {
    "es-MX": "Solo me falta:",
    "en": "I just need:",
}


def build_progress_summary(
    known_labels: list[str], language: Language, remaining_prompt: str | None = None
) -> str:
    """A checkmark-list recap of already-known fields ("Hasta ahora tengo: ✔ póliza ✔ cliente
    ..."), followed by remaining_prompt (the next question to ask) under a "Solo me falta:"
    lead-in. Returns remaining_prompt unchanged if known_labels is empty — there is nothing yet
    to recap, so this degrades to the plain, un-prefixed question exactly as before this PBI."""
    if not known_labels:
        return remaining_prompt or ""

    lines = [_HEADER.get(language) or _HEADER["es-MX"]]
    lines.extend(f"✔ {label}" for label in known_labels)
    if remaining_prompt:
        prefix = _REMAINING_PREFIX.get(language) or _REMAINING_PREFIX["es-MX"]
        lines.append(f"{prefix} {remaining_prompt}")
    return "\n".join(lines)

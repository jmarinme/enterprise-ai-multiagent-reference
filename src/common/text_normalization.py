"""Tiny shared text-normalization helper (PBI-09-01 final validation).

A live conversational test surfaced a real defect: "Juan Perez" (typed without the accent —
extremely common for Spanish names, especially over chat) failed to match the synthetic
customer record "Juan Pérez", because the lookup Tools compared strings with a plain
case-folded substring check and no accent normalization. `normalize_for_search` fixes this once,
shared by every synthetic name-search Tool, instead of duplicating the same `unicodedata` call in
each one.
"""

from __future__ import annotations

import unicodedata


def normalize_for_search(text: str) -> str:
    """Lowercase and strip accents/diacritics (NFKD-decompose, drop combining marks) so a name
    search is accent-insensitive — "perez" and "pérez" compare equal, "México" and "mexico"
    compare equal. Never used for anything but a search-key comparison; the original,
    accented text is always what is returned/displayed."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))

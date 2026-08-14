"""Server-side PII masking for observability data (PBI-13-01 §17). Applied before any
conversation/message text leaves the observability API — never in the frontend, never
optionally skippable by a client.

Pattern-based, not a full NLP/PII-detection pipeline (out of scope for V1) — covers the fields
explicitly named in PBI-13-01 §17: email, phone, and this platform's own synthetic policy
number format (SYN-POL-XXXXXXX, see src/services/tools/policy_lookup_tool.py's synthetic data).
"""

from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)[\s.-]?)?\d{3,4}[\s.-]?\d{3,4}\b")
_POLICY_NUMBER_RE = re.compile(r"\bSYN-POL-[A-Z0-9]{4,}\b", re.IGNORECASE)


def mask_pii(text: str | None) -> str | None:
    """Returns a copy of `text` with email/phone/policy-number-shaped substrings replaced by a
    fixed placeholder. None-safe (passes through None unchanged) so callers never need a
    separate null check."""
    if text is None:
        return None
    masked = _EMAIL_RE.sub("[email masked]", text)
    masked = _POLICY_NUMBER_RE.sub("[policy number masked]", masked)
    masked = _PHONE_RE.sub("[phone masked]", masked)
    return masked

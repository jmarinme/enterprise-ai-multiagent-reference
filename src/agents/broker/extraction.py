"""Deterministic field extraction for broker-services inquiries (PBI-01-06, bilingual keyword
coverage added by PBI-04-04, natural broker-name/period extraction added by PBI-05-01).

MockLLMProvider is intentionally content-agnostic and cannot perform real NLU, so every
business fact (which inquiry this is, which synthetic IDs were given, yes/no answers) must
come from regex/keyword rules here — same rationale as src.agents.claims.extraction.
"""

from __future__ import annotations

import re

from src.agents.broker.state import BrokerInquiryState, BrokerInquiryType
from src.agents.shared.nlu import resolve_commission_period, strip_natural_prefix

_BROKER_ID_PATTERN = re.compile(r"\b(SYN-BRK-\d{3,6}|BRK-SYN-\d{3,6})\b", re.IGNORECASE)
_POLICY_NUMBER_PATTERN = re.compile(r"\b(SYN-POL-\d{3,6})\b", re.IGNORECASE)
_TRANSACTION_REFERENCE_PATTERN = re.compile(r"\b(SYN-TXN-\d{3,6})\b", re.IGNORECASE)

# Checked in order (most distinctive keyword first, mirroring
# src.supervisor.intent.RuleBasedIntentResolver's own ordered-keyword-list pattern) so a
# message mentioning both "policy" and "commission" resolves to the more specific commission
# inquiry rather than the generic policy fallback. Bilingual (PBI-04-04).
_COMMISSION_KEYWORDS = ("commission", "comisión", "comision", "comisiones")
_TRANSACTION_KEYWORDS = ("transaction", "transacción", "transaccion")
_POLICY_KEYWORDS = ("policy", "coverage", "póliza", "poliza", "cobertura")

_PAYMENT_REQUEST_KEYWORDS = (
    "request payment",
    "submit payment",
    "submit a payment",
    "pay my commission",
    "process the payment",
    "process payment",
    "solicitar el pago",
    "solicitar pago",
    "pagar mi comisión",
    "pagar mi comision",
    "procesar el pago",
)

_FREE_TEXT_FALLBACK_FIELDS = {"broker_name"}

# "soy Synthetic Brokerage One", "somos Synthetic Brokerage One", "mi correduría es Synthetic
# Brokerage Two" (PBI-05-01 requirement 7) — captured proactively (not gated on last_asked_field)
# because the broker's own opening message often names itself and its intent in one turn: "Soy
# Synthetic Brokerage One y quiero conocer mis comisiones...". Stops at a natural delimiter
# (" y "/" and "/comma/period) so the trailing clause about commissions is never swept in.
_BROKER_NAME_PREFIX_PATTERN = re.compile(
    r"(?:mi correduría es|nuestra correduría es|somos|soy)\s+"
    r"([A-ZÁÉÍÓÚÑa-záéíóúñ0-9][\w .-]*?)"
    r"(?:\s+y\s+|\s+and\s+|,|\.|$)",
    re.IGNORECASE,
)
_NAME_PREFIXES: tuple[str, ...] = ("mi correduría es", "nuestra correduría es", "somos", "soy")


def extract_fields(message: str, state: BrokerInquiryState) -> BrokerInquiryState:
    """Return a copy of state with any recognizable fields from message filled in."""
    updated = state.model_copy()
    normalized = message.strip()
    lowered = normalized.lower()

    if updated.inquiry_type is None:
        if any(keyword in lowered for keyword in _COMMISSION_KEYWORDS):
            updated.inquiry_type = BrokerInquiryType.COMMISSION
        elif any(keyword in lowered for keyword in _TRANSACTION_KEYWORDS):
            updated.inquiry_type = BrokerInquiryType.TRANSACTION_STATUS
        elif any(keyword in lowered for keyword in _POLICY_KEYWORDS):
            updated.inquiry_type = BrokerInquiryType.POLICY_STATUS

    broker_match = _BROKER_ID_PATTERN.search(normalized)
    if broker_match:
        # A typed ID always short-circuits natural broker discovery (mirrors Claims' direct
        # policy number pattern) — matches both the legacy BRK-SYN-* and canonical SYN-BRK-*
        # namespaces, so the caller never needs to know which one their broker happens to use.
        updated.broker_id = broker_match.group(1).upper()

    if updated.broker_name is None and updated.broker_id is None:
        name_match = _BROKER_NAME_PREFIX_PATTERN.search(normalized)
        if name_match:
            updated.broker_name = name_match.group(1).strip(" ,.")

    policy_match = _POLICY_NUMBER_PATTERN.search(normalized)
    if policy_match:
        updated.policy_number = policy_match.group(1).upper()

    transaction_match = _TRANSACTION_REFERENCE_PATTERN.search(normalized)
    if transaction_match:
        updated.transaction_reference = transaction_match.group(1).upper()

    if updated.commission_period is None:
        period = resolve_commission_period(normalized)
        if period:
            updated.commission_period = period

    if (
        state.last_asked_field in _FREE_TEXT_FALLBACK_FIELDS
        and getattr(updated, state.last_asked_field) is None
        and normalized
    ):
        setattr(updated, state.last_asked_field, strip_natural_prefix(normalized, _NAME_PREFIXES))

    if updated.wants_payment_request is None and any(
        keyword in lowered for keyword in _PAYMENT_REQUEST_KEYWORDS
    ):
        updated.wants_payment_request = True

    return updated

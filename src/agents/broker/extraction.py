"""Deterministic field extraction for broker-services inquiries (PBI-01-06, bilingual keyword
coverage added by PBI-04-04).

MockLLMProvider is intentionally content-agnostic and cannot perform real NLU, so every
business fact (which inquiry this is, which synthetic IDs were given, yes/no answers) must
come from regex/keyword rules here — same rationale as src.agents.claims.extraction.
"""

from __future__ import annotations

import re

from src.agents.broker.state import BrokerInquiryState, BrokerInquiryType

_BROKER_ID_PATTERN = re.compile(r"\b(SYN-BRK-\d{3,6})\b", re.IGNORECASE)
_POLICY_NUMBER_PATTERN = re.compile(r"\b(SYN-POL-\d{3,6})\b", re.IGNORECASE)
_TRANSACTION_REFERENCE_PATTERN = re.compile(r"\b(SYN-TXN-\d{3,6})\b", re.IGNORECASE)
_COMMISSION_PERIOD_PATTERN = re.compile(r"\b(\d{4}-(?:Q[1-4]|[01]\d))\b", re.IGNORECASE)

_YES_WORDS = {"yes", "yeah", "yep", "affirmative", "correct", "si", "sí", "claro", "correcto"}
_NO_WORDS = {"no", "nope", "negative", "none", "para nada"}

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

_YES_NO_FIELDS = {"wants_payment_request"}


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
        updated.broker_id = broker_match.group(1).upper()

    policy_match = _POLICY_NUMBER_PATTERN.search(normalized)
    if policy_match:
        updated.policy_number = policy_match.group(1).upper()

    transaction_match = _TRANSACTION_REFERENCE_PATTERN.search(normalized)
    if transaction_match:
        updated.transaction_reference = transaction_match.group(1).upper()

    if updated.commission_period is None:
        period_match = _COMMISSION_PERIOD_PATTERN.search(normalized)
        if period_match:
            updated.commission_period = period_match.group(1).upper()

    if state.last_asked_field in _YES_NO_FIELDS and getattr(updated, state.last_asked_field) is None:
        first_word = lowered.split()[0].strip(",.!?") if lowered else ""
        if first_word in _YES_WORDS:
            setattr(updated, state.last_asked_field, True)
        elif first_word in _NO_WORDS:
            setattr(updated, state.last_asked_field, False)

    if updated.wants_payment_request is None and any(
        keyword in lowered for keyword in _PAYMENT_REQUEST_KEYWORDS
    ):
        updated.wants_payment_request = True

    return updated

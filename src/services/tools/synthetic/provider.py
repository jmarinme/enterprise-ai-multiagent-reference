"""Synthetic sample records for the Tool framework's proof-of-architecture Tools.

All data here is fabricated for demonstration only — no real TMX customers, policies, claims,
or brokers, and no real credentials. Deliberately small; this is not a dataset, it exists only
to prove the synthetic Tools (PolicyLookupTool, ClaimsStatusTool, BrokerAccountLookupTool,
PaymentStatusTool, ClaimRegistrationTool, AdjusterAssignmentTool) can return typed results
end-to-end. The SYN-POL-000x records additionally cover the four claims-intake scenarios
PBI-01-05 requires: active+paid, active+payment-issue, inactive, and not-found (any
unrecognized number).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SyntheticPolicyRecord(BaseModel):
    policy_number: str
    status: Literal["active", "lapsed", "cancelled"]
    holder_name: str
    line_of_business: str


class SyntheticClaimRecord(BaseModel):
    claim_number: str
    status: Literal["submitted", "under_review", "approved", "closed"]
    adjuster_name: str | None = None


class SyntheticBrokerRecord(BaseModel):
    broker_id: str
    broker_name: str
    status: Literal["active", "suspended"]
    commission_tier: str


SYNTHETIC_POLICIES: dict[str, SyntheticPolicyRecord] = {
    "POL-SYN-0001": SyntheticPolicyRecord(
        policy_number="POL-SYN-0001",
        status="active",
        holder_name="Synthetic Test Holder A",
        line_of_business="auto",
    ),
    "POL-SYN-0002": SyntheticPolicyRecord(
        policy_number="POL-SYN-0002",
        status="lapsed",
        holder_name="Synthetic Test Holder B",
        line_of_business="property",
    ),
}

SYNTHETIC_CLAIMS: dict[str, SyntheticClaimRecord] = {
    "CLM-SYN-0001": SyntheticClaimRecord(
        claim_number="CLM-SYN-0001",
        status="under_review",
        adjuster_name="Synthetic Adjuster A",
    ),
    "CLM-SYN-0002": SyntheticClaimRecord(
        claim_number="CLM-SYN-0002",
        status="closed",
        adjuster_name=None,
    ),
}

SYNTHETIC_BROKERS: dict[str, SyntheticBrokerRecord] = {
    "BRK-SYN-0001": SyntheticBrokerRecord(
        broker_id="BRK-SYN-0001",
        broker_name="Synthetic Brokerage A",
        status="active",
        commission_tier="gold",
    ),
    "BRK-SYN-0002": SyntheticBrokerRecord(
        broker_id="BRK-SYN-0002",
        broker_name="Synthetic Brokerage B",
        status="suspended",
        commission_tier="bronze",
    ),
}


class SyntheticPaymentStatusRecord(BaseModel):
    policy_number: str
    payment_current: bool
    last_payment_date: str | None = None


class SyntheticAdjusterRecord(BaseModel):
    adjuster_id: str
    adjuster_name: str
    region: str


# Claims-intake policy scenarios (PBI-01-05), additive to SYNTHETIC_POLICIES above:
#   SYN-POL-0001 -> active, payment current      (valid, no notices)
#   SYN-POL-0002 -> active, payment issue         (valid, surfaced as a fact, not a gate)
#   SYN-POL-0003 -> inactive (lapsed)              (surfaced as a fact, not a gate)
# Any other policy number (e.g. SYN-POL-9999) is simply absent -> "policy not found".
SYNTHETIC_POLICIES["SYN-POL-0001"] = SyntheticPolicyRecord(
    policy_number="SYN-POL-0001",
    status="active",
    holder_name="Synthetic Claimant One",
    line_of_business="auto",
)
SYNTHETIC_POLICIES["SYN-POL-0002"] = SyntheticPolicyRecord(
    policy_number="SYN-POL-0002",
    status="active",
    holder_name="Synthetic Claimant Two",
    line_of_business="auto",
)
SYNTHETIC_POLICIES["SYN-POL-0003"] = SyntheticPolicyRecord(
    policy_number="SYN-POL-0003",
    status="lapsed",
    holder_name="Synthetic Claimant Three",
    line_of_business="property",
)

SYNTHETIC_PAYMENT_STATUSES: dict[str, SyntheticPaymentStatusRecord] = {
    "SYN-POL-0001": SyntheticPaymentStatusRecord(
        policy_number="SYN-POL-0001", payment_current=True, last_payment_date="2026-07-01"
    ),
    "SYN-POL-0002": SyntheticPaymentStatusRecord(
        policy_number="SYN-POL-0002", payment_current=False, last_payment_date="2026-04-01"
    ),
    "SYN-POL-0003": SyntheticPaymentStatusRecord(
        policy_number="SYN-POL-0003", payment_current=False, last_payment_date=None
    ),
}

SYNTHETIC_ADJUSTERS: list[SyntheticAdjusterRecord] = [
    SyntheticAdjusterRecord(
        adjuster_id="ADJ-SYN-01", adjuster_name="Synthetic Adjuster Rivera", region="north"
    ),
    SyntheticAdjusterRecord(
        adjuster_id="ADJ-SYN-02", adjuster_name="Synthetic Adjuster Chen", region="south"
    ),
    SyntheticAdjusterRecord(
        adjuster_id="ADJ-SYN-03", adjuster_name="Synthetic Adjuster Okafor", region="central"
    ),
]


class SyntheticTransactionRecord(BaseModel):
    transaction_reference: str
    status: Literal["pending", "processing", "completed", "rejected"]
    description: str


class SyntheticCommissionRecord(BaseModel):
    broker_id: str
    commission_period: str
    amount: float
    status: Literal["available", "paid", "pending"]


# Broker-services scenarios (PBI-01-06), additive to SYNTHETIC_BROKERS above (new SYN-BRK-000x
# ID format, alongside the pre-existing BRK-SYN-000x records from PBI-01-02, which are kept
# unmodified since they are still referenced by PBI-01-02's own tests):
#   SYN-BRK-0001 -> active broker account
#   SYN-BRK-0002 -> active broker account (second broker, for cross-broker commission scenarios)
# Any other broker id (e.g. SYN-BRK-9999) is simply absent -> "broker not found".
SYNTHETIC_BROKERS["SYN-BRK-0001"] = SyntheticBrokerRecord(
    broker_id="SYN-BRK-0001",
    broker_name="Synthetic Brokerage One",
    status="active",
    commission_tier="gold",
)
SYNTHETIC_BROKERS["SYN-BRK-0002"] = SyntheticBrokerRecord(
    broker_id="SYN-BRK-0002",
    broker_name="Synthetic Brokerage Two",
    status="active",
    commission_tier="silver",
)

# Transaction-status scenarios: SYN-TXN-0001 completed, SYN-TXN-0002 pending. Any other
# reference is absent -> "transaction not found".
SYNTHETIC_TRANSACTIONS: dict[str, SyntheticTransactionRecord] = {
    "SYN-TXN-0001": SyntheticTransactionRecord(
        transaction_reference="SYN-TXN-0001",
        status="completed",
        description="Synthetic policy issuance request",
    ),
    "SYN-TXN-0002": SyntheticTransactionRecord(
        transaction_reference="SYN-TXN-0002",
        status="pending",
        description="Synthetic endorsement request",
    ),
}

# Commission scenarios, keyed by (broker_id, commission_period):
#   SYN-BRK-0001 / 2026-Q1 -> available (earned, not yet requested — eligible for payment)
#   SYN-BRK-0001 / 2026-Q2 -> paid (already paid out)
#   SYN-BRK-0002 / 2026-Q1 -> pending (earned but not yet finalized — not yet eligible)
# Any other (broker_id, commission_period) pair is absent -> "no commission found".
SYNTHETIC_COMMISSIONS: dict[tuple[str, str], SyntheticCommissionRecord] = {
    ("SYN-BRK-0001", "2026-Q1"): SyntheticCommissionRecord(
        broker_id="SYN-BRK-0001", commission_period="2026-Q1", amount=1250.00, status="available"
    ),
    ("SYN-BRK-0001", "2026-Q2"): SyntheticCommissionRecord(
        broker_id="SYN-BRK-0001", commission_period="2026-Q2", amount=980.50, status="paid"
    ),
    ("SYN-BRK-0002", "2026-Q1"): SyntheticCommissionRecord(
        broker_id="SYN-BRK-0002", commission_period="2026-Q1", amount=430.00, status="pending"
    ),
}

"""Synthetic sample records for the Tool framework's proof-of-architecture Tools.

All data here is fabricated for demonstration only — no real TMX customers, policies, claims,
or brokers, and no real credentials. Deliberately small; this is not a dataset, it exists only
to prove the synthetic Tools (PolicyLookupTool, ClaimsStatusTool, BrokerAccountLookupTool,
PaymentStatusTool, ClaimRegistrationTool, AdjusterAssignmentTool) can return typed results
end-to-end. The SYN-POL-000x records additionally cover the four claims-intake scenarios
PBI-01-05 requires: active+paid, active+payment-issue, inactive, and not-found (any
unrecognized number).

ID namespace note (PBI-05-01, CLAUDE.md §7 "smallest viable change"): several ID prefixes
coexist here for historical reasons (`POL-SYN-*`/`BRK-SYN-*` from the earliest Tool-framework
proof-of-concept, `SYN-POL-000x` from the claims-intake PBI, `SYN-BRK-*` from the broker-
services PBI). None were renamed or removed — many existing tests assert their exact IDs/field
values, and renaming would violate "do not break existing regression tests unnecessarily."
Instead, every **new** demo record added by PBI-05-01 uses one consistent canonical shape
(`CUS-SYN-000x` customers, `SYN-POL-1xxx` policies, `SYN-BRK-000x` brokers — already established
by PBI-04-04's customer-discovery work), and natural-language discovery (`customer_lookup`,
`broker_lookup`) searches every record regardless of which prefix it happens to use — so a
caller never needs to know or type an internal ID, old or new. See docs/sprint_05/decisions.md.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SyntheticPolicyRecord(BaseModel):
    policy_number: str
    status: Literal["active", "lapsed", "cancelled"]
    holder_name: str
    line_of_business: str
    # Optional, additive (PBI-04-04): a short human description ("Toyota Hilux 2021") used only
    # to let a caller disambiguate between a customer's own multiple policies in natural
    # language (e.g. "la Hilux", "la de auto") — never a source of a business fact by itself.
    vehicle_description: str | None = None
    # Optional, additive (PBI-05-01): the property-policy equivalent of vehicle_description —
    # a short human description used only for natural disambiguation ("la de hogar") and to
    # let ClaimsAgent's Property profile name the affected property in its own responses.
    property_description: str | None = None


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


class SyntheticCustomerRecord(BaseModel):
    customer_id: str
    full_name: str
    policy_numbers: list[str]


# Customer-discovery scenarios (PBI-04-04, expanded by PBI-05-01), additive, new SYN-POL-1xxx
# policy-number namespace so the pre-existing SYN-POL-000x direct-policy-number-first tests/
# scenarios are left byte-for-byte unchanged:
#   Juan Pérez     -> two active, payment-current auto policies (multi-policy disambiguation
#                     demo: "la primera"/"la segunda"/"la Hilux"/"el Sentra"/"la de auto")
#   Ana Torres     -> a single active property policy, payment NOT current (single-match
#                     auto-select demo; "active but payment-not-current" scenario)
#   Carlos Mendoza -> a single LAPSED auto policy (single-match demo; "lapsed policy, reachable
#                     through natural customer discovery, not just a direct policy number")
# Any other name has no match -> "customer not found".
SYNTHETIC_CUSTOMERS: dict[str, SyntheticCustomerRecord] = {
    "CUS-SYN-0001": SyntheticCustomerRecord(
        customer_id="CUS-SYN-0001",
        full_name="Juan Pérez",
        policy_numbers=["SYN-POL-1001", "SYN-POL-1002"],
    ),
    "CUS-SYN-0002": SyntheticCustomerRecord(
        customer_id="CUS-SYN-0002",
        full_name="Ana Torres",
        policy_numbers=["SYN-POL-1003"],
    ),
    "CUS-SYN-0003": SyntheticCustomerRecord(
        customer_id="CUS-SYN-0003",
        full_name="Carlos Mendoza",
        policy_numbers=["SYN-POL-1004"],
    ),
}

SYNTHETIC_POLICIES["SYN-POL-1001"] = SyntheticPolicyRecord(
    policy_number="SYN-POL-1001",
    status="active",
    holder_name="Juan Pérez",
    line_of_business="auto",
    vehicle_description="Nissan Sentra 2022",
)
SYNTHETIC_POLICIES["SYN-POL-1002"] = SyntheticPolicyRecord(
    policy_number="SYN-POL-1002",
    status="active",
    holder_name="Juan Pérez",
    line_of_business="auto",
    vehicle_description="Toyota Hilux 2021",
)
SYNTHETIC_POLICIES["SYN-POL-1003"] = SyntheticPolicyRecord(
    policy_number="SYN-POL-1003",
    status="active",
    holder_name="Ana Torres",
    line_of_business="property",
    property_description="Casa habitación, Colonia Del Valle, Ciudad de México",
)
SYNTHETIC_POLICIES["SYN-POL-1004"] = SyntheticPolicyRecord(
    policy_number="SYN-POL-1004",
    status="lapsed",
    holder_name="Carlos Mendoza",
    line_of_business="auto",
    vehicle_description="Honda CR-V 2019",
)

SYNTHETIC_PAYMENT_STATUSES["SYN-POL-1001"] = SyntheticPaymentStatusRecord(
    policy_number="SYN-POL-1001", payment_current=True, last_payment_date="2026-07-15"
)
SYNTHETIC_PAYMENT_STATUSES["SYN-POL-1002"] = SyntheticPaymentStatusRecord(
    policy_number="SYN-POL-1002", payment_current=True, last_payment_date="2026-07-15"
)
SYNTHETIC_PAYMENT_STATUSES["SYN-POL-1003"] = SyntheticPaymentStatusRecord(
    policy_number="SYN-POL-1003", payment_current=False, last_payment_date="2026-03-01"
)
SYNTHETIC_PAYMENT_STATUSES["SYN-POL-1004"] = SyntheticPaymentStatusRecord(
    policy_number="SYN-POL-1004", payment_current=False, last_payment_date="2025-11-01"
)


class SyntheticCoverageRecord(BaseModel):
    policy_number: str
    coverage_type: str
    limit_amount: float
    deductible: float


# Coverage scenarios (PBI-04-04): one record per policy that ClaimsAgent's business-validation
# step (CLAUDE.md §2's "coverage" fact-gathering, never adjudication) can report on. Covers
# every policy number ClaimsAgent's flow can reach, both the pre-existing SYN-POL-000x set and
# the new SYN-POL-1xxx customer-discovery set. Any other policy number is absent -> "coverage
# information not available".
SYNTHETIC_COVERAGES: dict[str, SyntheticCoverageRecord] = {
    "SYN-POL-0001": SyntheticCoverageRecord(
        policy_number="SYN-POL-0001",
        coverage_type="Cobertura amplia",
        limit_amount=250000.00,
        deductible=5000.00,
    ),
    "SYN-POL-0002": SyntheticCoverageRecord(
        policy_number="SYN-POL-0002",
        coverage_type="Cobertura amplia",
        limit_amount=250000.00,
        deductible=5000.00,
    ),
    "SYN-POL-0003": SyntheticCoverageRecord(
        policy_number="SYN-POL-0003",
        coverage_type="Cobertura básica de daños",
        limit_amount=150000.00,
        deductible=10000.00,
    ),
    "SYN-POL-1001": SyntheticCoverageRecord(
        policy_number="SYN-POL-1001",
        coverage_type="Cobertura amplia",
        limit_amount=280000.00,
        deductible=5000.00,
    ),
    "SYN-POL-1002": SyntheticCoverageRecord(
        policy_number="SYN-POL-1002",
        coverage_type="Cobertura amplia",
        limit_amount=320000.00,
        deductible=5000.00,
    ),
    "SYN-POL-1003": SyntheticCoverageRecord(
        policy_number="SYN-POL-1003",
        coverage_type="Cobertura básica de daños",
        limit_amount=150000.00,
        deductible=10000.00,
    ),
    # Lapsed policies still have a last-known coverage on file — reported as a fact (the
    # policy's lapsed status is what's surfaced as the caveat, not an absent coverage record).
    "SYN-POL-1004": SyntheticCoverageRecord(
        policy_number="SYN-POL-1004",
        coverage_type="Cobertura amplia",
        limit_amount=220000.00,
        deductible=7500.00,
    ),
}

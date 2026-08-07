"""Synthetic sample records for the Tool framework's proof-of-architecture Tools.

All data here is fabricated for demonstration only — no real TMX customers, policies, claims,
or brokers, and no real credentials. Deliberately small (two records per domain); this is not
a dataset, it exists only to prove PolicyLookupTool/ClaimsStatusTool/BrokerAccountLookupTool
can return typed results end-to-end.
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

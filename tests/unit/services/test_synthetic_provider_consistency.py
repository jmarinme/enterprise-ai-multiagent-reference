"""Referential-consistency tests for the synthetic demo dataset (PBI-05-01 requirement 18):
customer -> policy -> payment -> coverage, and broker -> commission, must never contain
contradictory records. These tests read src.services.tools.synthetic.provider's raw data
directly (not through a Tool) because the point is to validate the data itself, not any single
Tool's behavior — a Tool can only ever be as correct as the data it looks up.
"""

from src.services.tools.synthetic.provider import (
    SYNTHETIC_BROKERS,
    SYNTHETIC_COMMISSIONS,
    SYNTHETIC_COVERAGES,
    SYNTHETIC_CUSTOMERS,
    SYNTHETIC_PAYMENT_STATUSES,
    SYNTHETIC_POLICIES,
)

# The canonical, customer-linked policy namespace this PBI's demo portfolio lives in — the
# legacy POL-SYN-*/SYN-POL-000x records predate customer discovery and are deliberately not
# linked to any SyntheticCustomerRecord (see provider.py's own module docstring), so full
# customer->policy->payment->coverage consistency is only asserted for this namespace.
_CANONICAL_POLICY_PREFIX = "SYN-POL-1"


def test_every_customer_policy_number_exists_in_the_policy_table() -> None:
    for customer in SYNTHETIC_CUSTOMERS.values():
        for policy_number in customer.policy_numbers:
            assert policy_number in SYNTHETIC_POLICIES, (
                f"{customer.full_name} ({customer.customer_id}) references "
                f"unknown policy {policy_number!r}"
            )


def test_every_customer_policy_number_is_unique_within_that_customer() -> None:
    for customer in SYNTHETIC_CUSTOMERS.values():
        assert len(customer.policy_numbers) == len(set(customer.policy_numbers)), (
            f"{customer.full_name} lists a duplicate policy number"
        )


def test_no_policy_is_owned_by_more_than_one_customer() -> None:
    owners: dict[str, str] = {}
    for customer in SYNTHETIC_CUSTOMERS.values():
        for policy_number in customer.policy_numbers:
            assert policy_number not in owners, (
                f"policy {policy_number} is claimed by both {owners.get(policy_number)!r} "
                f"and {customer.full_name!r}"
            )
            owners[policy_number] = customer.full_name


def test_every_customer_linked_policys_holder_name_matches_the_customer() -> None:
    for customer in SYNTHETIC_CUSTOMERS.values():
        for policy_number in customer.policy_numbers:
            policy = SYNTHETIC_POLICIES[policy_number]
            assert policy.holder_name == customer.full_name, (
                f"policy {policy_number} holder_name {policy.holder_name!r} does not match "
                f"its owning customer {customer.full_name!r}"
            )


def test_every_canonical_policy_has_a_payment_status_record() -> None:
    canonical_policies = {
        number: record
        for number, record in SYNTHETIC_POLICIES.items()
        if number.startswith(_CANONICAL_POLICY_PREFIX)
    }
    assert canonical_policies, "expected at least one canonical (SYN-POL-1xxx) policy"
    for policy_number in canonical_policies:
        assert policy_number in SYNTHETIC_PAYMENT_STATUSES, (
            f"canonical policy {policy_number} has no payment status on file"
        )


def test_every_canonical_policy_has_a_coverage_record() -> None:
    canonical_policies = [n for n in SYNTHETIC_POLICIES if n.startswith(_CANONICAL_POLICY_PREFIX)]
    for policy_number in canonical_policies:
        assert policy_number in SYNTHETIC_COVERAGES, (
            f"canonical policy {policy_number} has no coverage record on file"
        )


def test_payment_status_records_reference_their_own_policy_number_consistently() -> None:
    for policy_number, record in SYNTHETIC_PAYMENT_STATUSES.items():
        assert record.policy_number == policy_number


def test_coverage_records_reference_their_own_policy_number_consistently() -> None:
    for policy_number, record in SYNTHETIC_COVERAGES.items():
        assert record.policy_number == policy_number


def test_auto_policies_have_a_vehicle_description_and_no_property_description() -> None:
    for policy_number, policy in SYNTHETIC_POLICIES.items():
        if not policy_number.startswith(_CANONICAL_POLICY_PREFIX):
            continue
        if policy.line_of_business == "auto":
            assert policy.vehicle_description, f"{policy_number} is auto but has no vehicle"
            assert policy.property_description is None, (
                f"{policy_number} is auto but also has a property_description"
            )


def test_property_policies_have_no_vehicle_description() -> None:
    for policy_number, policy in SYNTHETIC_POLICIES.items():
        if not policy_number.startswith(_CANONICAL_POLICY_PREFIX):
            continue
        if policy.line_of_business == "property":
            assert policy.vehicle_description is None, (
                f"{policy_number} is property but also has a vehicle_description"
            )


def test_every_commission_record_references_a_known_broker() -> None:
    for broker_id, _period in SYNTHETIC_COMMISSIONS:
        assert broker_id in SYNTHETIC_BROKERS, (
            f"commission record references unknown broker {broker_id!r}"
        )


def test_commission_records_reference_their_own_broker_id_and_period_consistently() -> None:
    for (broker_id, period), record in SYNTHETIC_COMMISSIONS.items():
        assert record.broker_id == broker_id
        assert record.commission_period == period


def test_every_broker_id_and_customer_id_is_unique() -> None:
    broker_ids = list(SYNTHETIC_BROKERS.keys())
    assert len(broker_ids) == len(set(broker_ids))
    customer_ids = [customer.customer_id for customer in SYNTHETIC_CUSTOMERS.values()]
    assert len(customer_ids) == len(set(customer_ids))


def test_demo_portfolio_covers_the_scenarios_pbi_05_01_requires() -> None:
    """A light structural check that the expanded portfolio actually contains the scenario
    variety PBI-05-01 requirement 16 asks for — not a business-logic assertion, just data
    coverage so a future edit cannot silently narrow the demo back down."""
    canonical_policies = [
        p for number, p in SYNTHETIC_POLICIES.items() if number.startswith(_CANONICAL_POLICY_PREFIX)
    ]
    statuses = {p.status for p in canonical_policies}
    assert "active" in statuses
    assert "lapsed" in statuses

    payment_flags = {
        SYNTHETIC_PAYMENT_STATUSES[number].payment_current
        for number in SYNTHETIC_PAYMENT_STATUSES
        if number.startswith(_CANONICAL_POLICY_PREFIX)
    }
    assert True in payment_flags
    assert False in payment_flags

    multi_policy_customers = [c for c in SYNTHETIC_CUSTOMERS.values() if len(c.policy_numbers) > 1]
    assert multi_policy_customers, "expected at least one customer with multiple policies"

    property_customers = [
        c
        for c in SYNTHETIC_CUSTOMERS.values()
        if any(SYNTHETIC_POLICIES[p].line_of_business == "property" for p in c.policy_numbers)
    ]
    assert property_customers, "expected at least one customer with a property policy"

    commission_statuses = {record.status for record in SYNTHETIC_COMMISSIONS.values()}
    assert "available" in commission_statuses
    assert "pending" in commission_statuses

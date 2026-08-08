"""Regression guard for the per-Agent Tool Calling allow-lists (PBI-02-04): every tool name in
every policy must actually be a registered Tool, so a typo in policies.py is caught by pytest
rather than surfacing only as a live ToolCallingError at runtime.
"""

from src.core.tool_calling.orchestrator import ToolCallingOrchestrator
from src.core.tool_calling.policies import (
    BROKER_ALLOWED_TOOLS,
    CLAIMS_ALLOWED_TOOLS,
    COMMERCIAL_ALLOWED_TOOLS,
)
from src.services.tools.adjuster_assignment_tool import AdjusterAssignmentTool
from src.services.tools.broker_account_lookup_tool import BrokerAccountLookupTool
from src.services.tools.claim_registration_tool import ClaimRegistrationTool
from src.services.tools.claims_status_tool import ClaimsStatusTool
from src.services.tools.commission_lookup_tool import CommissionLookupTool
from src.services.tools.commission_payment_request_tool import CommissionPaymentRequestTool
from src.services.tools.coverage_lookup_tool import CoverageLookupTool
from src.services.tools.customer_lookup_tool import CustomerLookupTool
from src.services.tools.lead_registration_tool import LeadRegistrationTool
from src.services.tools.payment_status_tool import PaymentStatusTool
from src.services.tools.policy_lookup_tool import PolicyLookupTool
from src.services.tools.transaction_status_tool import TransactionStatusTool
from src.tools.executor import ToolExecutor
from src.tools.registry import InMemoryToolRegistry


def _full_registry() -> InMemoryToolRegistry:
    """Every synthetic Tool registered — mirrors apps/api/src/api/dependencies.py's
    get_tool_registry(), rebuilt locally so this test package never depends on apps/api."""
    registry = InMemoryToolRegistry()
    registry.register(PolicyLookupTool())
    registry.register(ClaimsStatusTool())
    registry.register(BrokerAccountLookupTool())
    registry.register(PaymentStatusTool())
    registry.register(ClaimRegistrationTool())
    registry.register(AdjusterAssignmentTool())
    registry.register(TransactionStatusTool())
    registry.register(CommissionLookupTool())
    registry.register(CommissionPaymentRequestTool())
    registry.register(LeadRegistrationTool())
    registry.register(CustomerLookupTool())
    registry.register(CoverageLookupTool())
    return registry


def test_claims_allowed_tools_are_all_registered() -> None:
    registry = _full_registry()
    orchestrator = ToolCallingOrchestrator(
        tool_registry=registry,
        tool_executor=ToolExecutor(tool_registry=registry),
        llm_provider=None,  # type: ignore[arg-type]
    )

    definitions = orchestrator.build_tool_definitions(list(CLAIMS_ALLOWED_TOOLS))

    assert {definition.name for definition in definitions} == set(CLAIMS_ALLOWED_TOOLS)


def test_broker_allowed_tools_are_all_registered() -> None:
    registry = _full_registry()
    orchestrator = ToolCallingOrchestrator(
        tool_registry=registry,
        tool_executor=ToolExecutor(tool_registry=registry),
        llm_provider=None,  # type: ignore[arg-type]
    )

    definitions = orchestrator.build_tool_definitions(list(BROKER_ALLOWED_TOOLS))

    assert {definition.name for definition in definitions} == set(BROKER_ALLOWED_TOOLS)


def test_commercial_allowed_tools_are_all_registered() -> None:
    registry = _full_registry()
    orchestrator = ToolCallingOrchestrator(
        tool_registry=registry,
        tool_executor=ToolExecutor(tool_registry=registry),
        llm_provider=None,  # type: ignore[arg-type]
    )

    definitions = orchestrator.build_tool_definitions(list(COMMERCIAL_ALLOWED_TOOLS))

    assert {definition.name for definition in definitions} == set(COMMERCIAL_ALLOWED_TOOLS)


def test_policies_do_not_overlap_unexpectedly_between_claims_and_commercial() -> None:
    """Claims and Commercial serve different lines of business with no shared Tool need
    (CLAUDE.md §2) — Broker intentionally does share policy_lookup with Claims (documented in
    docs/sprint_02/decisions.md), so only this pair is asserted disjoint."""
    assert set(CLAIMS_ALLOWED_TOOLS).isdisjoint(COMMERCIAL_ALLOWED_TOOLS)

"""Regression tests (PBI-09-01 final validation): a live conversational test found that typing
a Spanish name without its accent ("Juan Perez") failed to match the synthetic customer record
"Juan Pérez", because CustomerLookupTool/BrokerLookupTool compared strings with a plain
case-folded substring check and no accent normalization — a very common, realistic input
variance for Spanish names over chat. Fixed via src.common.text_normalization.
"""

from __future__ import annotations

from src.services.tools.broker_lookup_tool import BrokerLookupInput, BrokerLookupTool
from src.services.tools.customer_lookup_tool import CustomerLookupInput, CustomerLookupTool
from src.tools.models import ToolExecutionContext

_CTX = ToolExecutionContext()


async def test_customer_lookup_finds_a_match_when_the_query_omits_the_accent() -> None:
    tool = CustomerLookupTool()

    result = await tool.execute(CustomerLookupInput(full_name="Juan Perez"), _CTX)

    assert result.success
    assert result.data is not None
    assert any(match.full_name == "Juan Pérez" for match in result.data.matches)


async def test_customer_lookup_finds_a_match_when_the_query_has_an_extra_accent() -> None:
    """The reverse case: a record's own name might be typed with an accent the caller didn't
    use, or vice versa — normalization must be symmetric."""
    tool = CustomerLookupTool()

    result = await tool.execute(CustomerLookupInput(full_name="Ána Torres"), _CTX)

    assert result.success
    assert result.data is not None
    assert any(match.full_name == "Ana Torres" for match in result.data.matches)


async def test_broker_lookup_is_accent_insensitive_too() -> None:
    tool = BrokerLookupTool()

    result = await tool.execute(BrokerLookupInput(full_name="Synthëtic Brokerage One"), _CTX)

    assert result.success
    assert result.data is not None
    assert any(match.broker_id == "SYN-BRK-0001" for match in result.data.matches)

"""Small, purely mechanical helpers shared across multi-turn Agents (Claims, Broker,
Commercial Intake).

Extracted in PBI-01-07 once a third agent needed the exact same patterns already duplicated
between ClaimsAgent (PBI-01-05) and BrokerAgent (PBI-01-06) — the "rule of three" trigger
PBI-01-06's decisions.md flagged. Deliberately narrow: only logic with zero real per-agent
variation (beyond already-parameterized inputs) lives here. State-machine business logic,
field extraction, and Tool orchestration remain domain-specific in each Agent's own
subpackage — see docs/sprint_01/decisions.md for what was considered and NOT extracted.
"""

from __future__ import annotations

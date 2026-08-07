"""Orchestration, routing, guardrails, permissions, resilience, and context management
(CLAUDE.md §6). tool_calling (PBI-02-04) is the first framework hosted here: it enforces the
per-Agent Tool allow-list (a permissions concern) and runs the LLM<->Tool loop (an
orchestration concern) — Supervisor routing itself remains in src/supervisor/.
"""

from __future__ import annotations

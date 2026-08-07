# Sprint 01 Implementation Plan

## PBI-01-01 — Supervisor Agent orchestration framework

Builds the reusable orchestration pipeline (Supervisor → Conversation Context → Intent
Resolver → Agent Registry → Selected Agent → Agent Response → Conversation Repository)
entirely behind Protocol interfaces, with a rule-based intent resolver and three deterministic
mock agents to validate the registry pattern end-to-end via `POST /chat`. No LLM, no RAG, no
Azure OpenAI, no real business logic. See `docs/sprint_01/decisions.md` for the Docker
build-context fix required to keep the API image buildable once it depends on the shared
`src/` packages, and `docs/sprint_00/decisions.md` for the explicit Sprint 00→01 sequencing
decision.

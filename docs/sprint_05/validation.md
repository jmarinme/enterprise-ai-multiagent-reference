# Sprint 05 Validation

Record only commands actually executed and their real results.

## PBI-05-01

### Backend — final regression (2026-08-08, after all five live-validation bugs were fixed)

| Command | Result |
|---|---|
| `python -m pytest -q` | **551 passed, 2 skipped**, 4.61s. (2 skips are pre-existing, unrelated to this PBI — Cosmos-adapter tests that require a real connection string.) |
| `python -m ruff check .` | All checks passed. |
| `python -m mypy src apps/api/src` | Success: no issues found in 124 source files. |

New/changed test files exercised by the run above (all passing): `tests/unit/agents/shared/test_nlu.py` (19 tests), `tests/unit/agents/shared/test_conversational_policy.py` (6 tests), `tests/unit/services/test_synthetic_provider_consistency.py` (14 tests), `tests/unit/agents/claims/{test_state,test_extraction,test_workflow}.py`, `tests/unit/agents/broker/{test_broker_state,test_broker_workflow}.py`, `tests/unit/agents/commercial/test_commercial_extraction.py`, `tests/unit/agents/test_{claims_agent_functional,claims_agent_knowledge_integration,broker_agent_functional}.py`, `tests/unit/api/test_chat.py` (incl. new `test_chat_hands_off_from_claims_to_broker_and_preserves_claims_state`), `tests/unit/core/tool_calling/test_policies.py`, `tests/unit/services/test_in_memory_conversation_repository.py`, `tests/unit/supervisor/{test_intent,test_orchestrator}.py`.

### Frontend — final regression (2026-08-08)

| Command | Result |
|---|---|
| `npm run test -- --run` (apps/web) | **8 test files passed, 33 tests passed.** (Two expected `ECONNREFUSED`/fetch-failure stderr lines are from a deliberate negative-path test exercising the "no backend reachable" UI state — not failures.) |
| `npm run typecheck` (apps/web) | No output — 0 errors. |
| `npm run lint` (apps/web) | No output — 0 errors. |

No frontend source file was changed this PBI (see `decisions.md`), so this run is a no-regression confirmation, not new-feature coverage. `npm run build` was not re-run in this final pass because no frontend file changed since the last confirmed-green build; the deployed `ca-tmxap-dev-web` image predates this PBI and was not rebuilt (see Deployment below).

### Deployment

| Step | Result |
|---|---|
| Build `tmxap-api` via `az acr build` (ACR remote build, repo-root context, `apps/api/Dockerfile`) | Succeeded — confirmed via `az acr task list-runs --top 1 --query '[0].status'` = `Succeeded` each time (5 rebuild cycles total, one per bug fix). Final tag: `dev-20260808124351-pbi0501`. |
| `az containerapp update -n ca-tmxap-dev-api -g rg-tmx-agent-platform-dev --image ...` | Succeeded each cycle — new revision created each time (unique tag per PBI-04-01's versioning decision, no `--revision-suffix` needed). Current revision: `ca-tmxap-dev-api--0000016`, `healthState: Healthy`. |
| `ca-tmxap-dev-web` | **Not rebuilt, not redeployed** — no frontend change this PBI. Running image `dev-20260808090031` predates this PBI (last built in an earlier sprint). |
| `GET /health` (API) | `200` (re-confirmed 2026-08-08, after final regression). |
| `GET /` (Web) | `200` (re-confirmed 2026-08-08). |

No Azure resource was created, deleted, or reconfigured (RBAC/networking unchanged) — only the existing `ca-tmxap-dev-api` Container App's revision was updated, exactly as authorized.

### Live DEV validation — the four mandated scenarios

All four driven against the real deployed DEV API (`https://ca-tmxap-dev-api.bluemushroom-e2f74836.eastus2.azurecontainerapps.io`) using a UTF-8-safe Python helper script (`chat_turn.py`) rather than raw bash/curl arguments, which mangle accented Spanish characters in this Windows Git-Bash environment.

**Scenario A — Auto claim (Juan Pérez / "La Hilux", rich multi-fact message).**
Result: customer resolved by name via `customer_lookup`; two-policy disambiguation resolved by "La Hilux."; a rich multi-clause message ("Ayer me chocaron por atrás en Reforma. Yo manejaba, no hubo lesionados ni terceros y el vehículo todavía puede circular.") correctly extracted `event_date` (relative "ayer" resolved), `event_location = "Reforma"`, `loss_type = "collision"`, `injuries_reported = False`, `third_parties_involved = False`, `vehicle_drivable = True`, all from one turn, in one Tool-backed pass. Confirmation gate presented before claim registration; claim registered only after explicit "sí." **Bugs #1, #2 found and fixed during this scenario.**

**Scenario B — Property claim (synthetic Property customer, rich multi-fact message).**
Result: LOB correctly resolved to `property` from the authoritative `policy_lookup` result; Property-specific field groups (affected area, contents, habitability) asked instead of vehicle/driver questions; a rich message directly answering "¿Dónde ocurrió el incidente?" while also mentioning an unrelated fact (no injuries) correctly captured both `event_location` and `injuries_reported`/`property_habitable` from the same turn. **Bugs #3, #4, #5 found and fixed during this scenario.**

**Scenario C — Broker handoff mid-Claims (natural broker name + natural period).**
Result: mid-Claims conversation, "Ahora quiero consultar mis comisiones." triggered explicit Supervisor handoff to `BrokerAgent`; broker resolved via "soy Synthetic Brokerage One"-style natural name, period resolved via natural expression (e.g. "primer trimestre de 2026"); commission amount ($1,250.00, 2026-Q1) reported in natural Spanish with no raw broker/period ID exposed; the next ambiguous follow-up correctly stayed with `BrokerAgent` rather than being naively keyword-matched back to Claims — confirming the `current_agent` persistence fix. No bugs found in this scenario.

**Scenario D — Commercial handoff from the same conversation.**
Turn 1: "Ahora necesito una cotización para mi empresa." → Supervisor correctly handed off to `CommercialIntakeAgent`, which asked "¿Cuál es el nombre de tu empresa o negocio?" — no stale Broker-flow artifact ("¿Te gustaría solicitar el pago...?") leaked into the response.
Turn 2: "Consultoría Acme" → correctly captured as `company_name`, immediately asked the next natural question ("¿Cuál es el nombre completo de la persona de contacto?") — no re-ask of company name, no Claims/Broker state visible in the response. `currentAgent` confirmed as `CommercialIntakeAgent` via the conversation-history endpoint. No bugs found in this scenario. (The public `GET /conversations/{id}` response deliberately excludes internal `metadata` — by design, per CLAUDE.md §10's "do not store hidden chain-of-thought... only redacted metadata" — so state-carry-forward correctness across this exact handoff chain is verified at the repository level instead, by `tests/unit/api/test_chat.py::test_chat_hands_off_from_claims_to_broker_and_preserves_claims_state`, which exercises the identical `carry_forward_other_agent_state` code path shared by all three Agents.)

### Summary of live-validation outcome

4/4 mandated scenarios completed successfully. 5 real bugs found, fixed, regression-tested, and re-deployed during the process (see `decisions.md` for full root-cause detail) — none reported by the user; all self-discovered by actually executing the PBI's own mandated validation scenarios with realistically rich Spanish input, consistent with the pattern PBI-04-04 established.

# Sprint 10 — Validation

## PBI-10-06

This PBI was documentation-only (CLAUDE.md §7.1/§11 — "if validation cannot run, explain why").
No application code, test, or infrastructure file was modified, so no lint/type/unit/contract/
integration/conversational/E2E validation applies. Validation performed instead: cited evidence
was re-verified directly against the current repository rather than trusted from memory or the
prior review.

| Command / check | Result |
|---|---|
| `python -m pytest tests/ --collect-only -q` | `684 tests collected` — used to correct the executive summary's stale "649 passing tests" figure |
| `npx vitest run --reporter=basic` (in `apps/web/`) | `Test Files 8 passed (8)`, `Tests 40 passed (40)` — used to add the frontend test count to the executive summary, which previously omitted it |
| `Grep "def test_"` on `tests/unit/api/test_auth.py` | 24 test functions confirmed, matching every specific test name cited in `02_security_review.md`, `04_risk_register.md`, and `05_executive_summary.md` |
| Direct read of `tests/unit/api/test_cors.py` | 10 test functions confirmed, matching the CORS-fix citations added throughout |
| `Grep "def test_validator_rejects_the_legacy_application_id_uri_as_audience"` | Confirmed present — cited in `Deployment_Guide.md`'s troubleshooting table |
| File-existence check for every new/changed relative Markdown link (`test -f`) | All resolved: ADR-0010 from `review/*.md` (`../docs/Architecture/adr/0010-...md`), from `docs/Architecture/*.md` (`adr/0010-...md`), from `docs/Architecture/diagrams/*.md` (`../adr/0010-...md`); the new diagram file from README, ADR-0010, and `networking-topology.md` |
| `ls docs/Architecture/adr/` | `0001`–`0010`, sequential, no gaps or duplicates |
| `python -c "from docx import Document; ..."` (heading + figure caption dump) | `Manual_de_Usuario.docx` regenerated successfully; heading structure includes new §3.1–3.6; figure captions sequential (`1a`/`1b`/`1c` placeholders, then `2`–`10` for the 9 real screenshots — no duplicate or out-of-order numbers) |
| `ls docs/sprint_00` … `docs/sprint_09` | Confirmed `docs/sprint_10/` and `docs/sprint_11/` did not exist before this sprint — the basis for `decisions.md` D-02 |

## Known gaps carried forward (not fixed by this PBI, out of its scope)

- `docs/sprint_11/` (Microsoft Entra ID authentication PBIs, PBI-11-01 through PBI-11-01D) was
  never created and was not retroactively backfilled here — see `decisions.md` D-02.
- Three sign-in-flow screenshots remain pending capture (placeholder captions, no image) — see
  `decisions.md` D-03.
- Pre-existing 9 screenshots in `Manual_de_Usuario.docx` predate the Entra ID header change
  (account name + sign-out button) and were not recaptured — their conversation content remains
  accurate; only the header chrome is stale.

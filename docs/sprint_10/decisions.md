# Sprint 10 — Decisions

## D-01: Documentation-only scope, strictly enforced

**Decision**: PBI-10-06 touched only Markdown/`.docx` documentation and one Python build script
(`build_docx.py`, outside the repository, used to regenerate `Manual_de_Usuario.docx`). No file
under `apps/`, `src/`, `tests/`, or `ops/` was modified.

**Why**: explicit user instruction for this PBI ("DO NOT: modify application code, modify tests,
modify infrastructure, deploy, commit, push"), consistent with CLAUDE.md §7's "make the smallest
viable change that completes the current PBI."

## D-02: `docs/sprint_11/` was not retroactively created

**Decision**: The Microsoft Entra ID authentication PBIs (PBI-11-01, PBI-11-01A, PBI-11-01B,
PBI-11-01C, PBI-11-01D) were implemented, tested, and deployed to DEV in an earlier session, but
no `docs/sprint_11/` folder was ever created for them — confirmed by directory listing
(`docs/sprint_00` through `docs/sprint_09` exist; `sprint_10`/`sprint_11` did not, before this
sprint). This sprint did not backfill `docs/sprint_11/`.

**Why**: PBI-10-06's own instructions scope this pass to specific named documents (README,
guides, ADR, review) and explicitly forbid inventing content. Reconstructing a full
`sprint_11/README.md` + `implementation-plan.md` + `decisions.md` + `validation.md` set after the
fact, without having been present for those PBIs' actual execution, risks presenting
reconstructed narrative as original evidence — the opposite of this review's own "use repository
evidence only" standard. The real, verifiable evidence for that work (code, tests, ADR-0010, the
live DEV deployment state) is cited directly throughout this sprint's documentation updates
instead.

**Follow-up recommendation**: a future PBI should create `docs/sprint_11/` with an honest
after-the-fact account (explicitly dated/labeled as reconstructed where necessary), or the
project should accept and document this as a one-time process gap rather than leave it silently
unaddressed indefinitely.

## D-03: Sign-in screenshots left as pending-capture placeholders, not fabricated

**Decision**: `Manual_de_Usuario.docx`'s three new sign-in-flow figures (1a/1b/1c) are
caption-only placeholders marked "[Captura pendiente]," not embedded images. The pre-existing 9
screenshots (sidebar, chat, and all 5 business scenarios) were kept as-is.

**Why**: no screenshot of the live Microsoft Entra ID sign-in flow exists in this repository's
screenshot evidence directory, and capturing one requires a real, interactive Microsoft
sign-in — not something this session could perform (no human present to complete an interactive
Entra ID login, and doing so is also outside this PBI's documentation-only, no-deployment scope).
Fabricating a screenshot, or silently reusing an unrelated image, would violate the explicit
"use repository evidence only" instruction. The pre-existing 9 screenshots were kept because they
still accurately depict the conversation content of each business scenario; their header chrome
(no account name/sign-out button, since they predate Entra ID) is a minor, explicitly-acceptable
staleness compared to fabricating new ones.

## D-04: Risk register renumbering (RISK-025/RISK-026, not RISK-001/RISK-002 removal)

**Decision**: RISK-001 ("No authentication exists") and RISK-002 ("IDOR") were moved to the
Resolved findings section as new entries RISK-025 and RISK-026, rather than deleted or
renumbered in place.

**Why**: `04_risk_register.md`'s own existing convention (RISK-022/023/024) keeps resolved
findings as new numbered entries with a "Formerly RISK-00N" cross-reference, preserving the
original ID for audit-trail purposes (CLAUDE.md §12's "do not erase previous entries"). Reusing
RISK-001/RISK-002's numbers for something else in the future would create ambiguity in any
external reference to those IDs (e.g., this sprint's own `README.md` Deliverable Log, prior
session notes) made before this change.

# Sprint 00 Decisions and Deviations

Record sprint-specific decisions and deviations. Cross-sprint decisions belong in ADRs.

## 2026-08-05 — Git risk resolved; repository connected to GitHub

**Decision:** Git is confirmed installed (`2.55.0.windows.3`). The repository has been initialized locally, an initial commit was created, and it has been pushed to the GitHub remote `origin` at https://github.com/jmarinme/enterprise-ai-multiagent-reference. Local `main` tracks `origin/main`.

**Deviation/status change:** The previously identified technical risk "Git not installed / repository not under version control" is closed. The `CLAUDE.md` §15 branch-per-PBI and commit workflow can now be followed for subsequent PBIs.

**Scope note:** This update is documentation-only. No PBI has been implemented or marked complete as part of this change.

## 2026-08-06 — Branch topology note: PBI-00-01 completion commit not reachable from this branch

**Observation:** `feat/pbi-00-02-api-foundation` (and `main`) currently point at commit `7806daa` ("docs(sprint-00): record Git and GitHub initialization"). A later commit, `4b21a3f` ("docs(sprint-00): complete PBI-00-01 repository validation"), exists in the local repository object database but is not reachable from any branch — `main` was not advanced to it before this feature branch was cut. As a result, `docs/sprint_00/README.md`/`validation.md`/`decisions.md` on this branch do not show the PBI-00-01 checkbox/log/evidence.

**Deviation/status change:** None applied here — this is a report of existing branch state, not a fix. Rewriting branch history (rebase, cherry-pick, or resetting `main`) is a git operation with irreversible-risk characteristics and was not performed without explicit authorization. PBI-00-02 work proceeds on top of the current branch state per explicit instruction to execute PBI-00-02 only.

**How to apply:** Before closing Sprint 00, reconcile branches so `4b21a3f`'s PBI-00-01 evidence is reachable from `main` (e.g., merge or cherry-pick), otherwise the sprint's git history will not reflect that PBI-00-01 was completed.

## 2026-08-06 — PBI-00-02: Python interpreter version deviation

**Decision:** `apps/api/pyproject.toml` declares `requires-python = ">=3.12"` per `CLAUDE.md` §5, matching the target runtime. Local validation (pytest, ruff, mypy, and the runtime smoke test) was executed using the only interpreter available in this environment, Python 3.11.9, inside an isolated venv at `apps/api/.venv`.

**Deviation/status change:** This is the same pre-existing environment gap recorded 2026-08-05 (R-01 in `docs/sprint_00/implementation-plan.md`). No 3.12-only language features were used in the code written for PBI-00-02, so the 3.11.9 validation results are expected to hold under 3.12, but this has not been confirmed on the actual required interpreter. Marked as a known condition, not a blocker.

**How to apply:** Install Python 3.12 and re-run `pytest`/`ruff`/`mypy` against it before this code is considered fully compliant with `CLAUDE.md` §5, ideally before Sprint 00 closes.

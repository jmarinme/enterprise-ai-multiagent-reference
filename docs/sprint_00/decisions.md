# Sprint 00 Decisions and Deviations

Record sprint-specific decisions and deviations. Cross-sprint decisions belong in ADRs.

## 2026-08-05 — Git risk resolved; repository connected to GitHub

**Decision:** Git is confirmed installed (`2.55.0.windows.3`). The repository has been initialized locally, an initial commit was created, and it has been pushed to the GitHub remote `origin` at https://github.com/jmarinme/enterprise-ai-multiagent-reference. Local `main` tracks `origin/main`.

**Deviation/status change:** The previously identified technical risk "Git not installed / repository not under version control" is closed. The `CLAUDE.md` §15 branch-per-PBI and commit workflow can now be followed for subsequent PBIs.

**Scope note:** This update is documentation-only. No PBI has been implemented or marked complete as part of this change.

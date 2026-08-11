# Sprint 10 — Implementation Plan

## PBI-10-06: Final Documentation Refresh After Microsoft Entra ID Integration

### Objective

Propagate the completed, live-in-DEV Microsoft Entra ID authentication implementation
(PBI-11-01 through PBI-11-01D) into every architecture and operational document that still
described the pre-authentication state, using only repository evidence — no invented
functionality, no full document rewrites, existing style/numbering/tables preserved.

### Plan

1. Inspect current state of every named document plus the existing review artifacts and ADR
   template/numbering — no edits yet.
2. Create `docs/Architecture/adr/0010-enterprise-authentication-entra-id.md` (Context, Decision,
   Alternatives considered, Why OAuth2 PKCE / MSAL / JWT / JWKS / tid+oid, Security implications,
   Consequences), matching ADR-0001–0009's established template.
3. Update `README.md`: add Features, Security, Authentication, Architecture Overview, Technology
   Stack sections (did not previously exist) — Spanish, matching the file's existing tone.
4. Update `docs/Architecture/Deployment_Guide.md`: App Registration/redirect URIs/API scope,
   `ENTRA_*`/`VITE_ENTRA_*` variables, authentication smoke test, common deployment issues
   (CORS header, audience GUID vs. Application ID URI, redirect-bridge requirement).
5. Update `docs/Architecture/Administrator_Guide.md`: new "Enterprise Authentication
   Administration" subsection (App Registration, SPA config, redirect URIs, Expose an API/
   `access_as_user`, JWT validation overview, troubleshooting, user onboarding, external users).
6. Update `docs/Architecture/User_Guide.md` and `Manual_de_Usuario.md`: real sign-in
   documentation (sign in with Microsoft, select account, authenticated session, session
   expiration, conversation history after login, sign out), replacing the "no authentication"
   framing.
7. Regenerate `Manual_de_Usuario.docx` from the updated `.md`, reusing the existing python-docx
   build script pattern and existing captured screenshots; new sign-in figures left as
   pending-capture placeholders (no fabricated images — see `decisions.md` D-03).
8. Re-run the architecture/security review from scratch against the current repository (not
   reusing prior conclusions): `00_project_inventory.md`, `01_architecture_review.md` §2e,
   `02_security_review.md` §3b + OWASP table + summary counts, `04_risk_register.md`
   (RISK-001/002 → resolved as RISK-025/026), `05_executive_summary.md` (findings, risk
   dashboard, readiness score, Go/No-Go, §7 reframe, action items, output summary).
9. Add the previously-missing authentication/request-flow diagram
   (`docs/Architecture/diagrams/authentication-request-flow.md`) and cross-reference it from the
   pre-existing `networking-topology.md` (which is network-layer-only and does not show
   authentication) and from ADR-0010/README.
10. Final validation pass: verify every new/changed internal link resolves, ADR numbering has no
    gaps/duplicates, cited test names exist in the actual test files, and re-verify current
    backend/frontend test counts directly (not from memory).
11. Create this sprint's own documentation (`docs/sprint_10/`) per CLAUDE.md §12/§13.

### Files planned for creation or modification

See `README.md`'s Deliverable Log for the final, as-executed list.

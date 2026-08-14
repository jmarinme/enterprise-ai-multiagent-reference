# PBI-14-03 — Test Evidence Summary

Captured 2026-08-13, branch `feat/pbi-14-03-multiagent-semantic-intelligence`.

```
$ python -m pytest tests/unit tests/conversational -q
796 passed, 1 warning in ~15s

$ python -m ruff check .
All checks passed!

$ python -m mypy src apps/api
Found 7 errors in 1 file (checked 162 source files)
  -> all 7 in src/pipelines/knowledge_ingestion/index_schema.py, pre-existing,
     confirmed untouched via `git status`/`git diff` this session.

$ cd apps/web && npm run test -- --run
Test Files  8 passed (8)
     Tests  42 passed (42)

$ cd apps/web && npm run typecheck
(no output — clean)

$ cd apps/web && npm run lint
(no output — clean)

$ cd apps/web && npm run build
219 modules transformed, built in 1.81s — no errors
```

See `docs/sprint_14/validation.md` for the full commentary and `decisions.md` for what was
intentionally not built or verified.

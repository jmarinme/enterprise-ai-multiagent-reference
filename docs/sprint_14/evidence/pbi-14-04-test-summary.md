# PBI-14-04 — Test Evidence Summary

Captured 2026-08-14, branch `feat/pbi-14-04-universal-semantic-routing`.

```
$ python -m pytest tests/unit tests/conversational -q
851 passed, 1 warning in ~18s

$ python -m ruff check .
All checks passed!

$ python -m mypy src apps/api
Found 7 errors in 1 file (checked 163 source files)
  -> all 7 in src/pipelines/knowledge_ingestion/index_schema.py, pre-existing,
     confirmed untouched via `git status`/`git diff` this session (identical to the
     PBI-14-03 evidence capture).

$ cd apps/web && npm run test -- --run
Test Files  9 passed (9)
     Tests  50 passed (50)

$ cd apps/web && npm run typecheck
(no output — clean)

$ cd apps/web && npm run lint
(no output — clean)

$ cd apps/web && npm run build
219 modules transformed, built in ~2s — no errors
```

See `docs/sprint_14/validation.md` for full commentary and `decisions.md` for what was
intentionally not built or verified (real Azure OpenAI classification quality for the
paraphrase test cases, in particular).

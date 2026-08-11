# PBI-09-01 Test Evidence

## Full suite, after PBI-09-01 changes

```
$ .venv/Scripts/python.exe -m pytest -q
633 passed, 2 skipped, 1 warning in 15.11s
```

(2 skips are pre-existing, unrelated to this PBI.)

## New PBI-09-01 tests, isolated run

```
$ .venv/Scripts/python.exe -m pytest tests/conversational/test_global_memory_and_multi_domain_orchestration.py \
    tests/unit/agents/shared/test_memory.py tests/unit/agents/shared/test_summary.py \
    tests/unit/agents/shared/test_nlu.py tests/unit/agents/claims/test_extraction.py -q
64 passed, 1 warning in 0.96s
```

## Static analysis

```
$ .venv/Scripts/python.exe -m ruff check <touched files>
All checks passed!

$ .venv/Scripts/python.exe -m mypy <touched src files>
Success: no issues found in 9 source files
```

## Baseline (before this PBI, for comparison)

```
$ .venv/Scripts/python.exe -m pytest -q
612 passed, 2 skipped, 1 warning in 18.29s
```

## PBI-09-01 Final Conversational Validation (2026-08-10)

Live scenario transcripts: `docs/sprint_09/evidence/final-validation-scenario-transcripts.txt`
(14 scenarios, all clean after fixes).

```
$ .venv/Scripts/python.exe -m pytest -q
649 passed, 2 skipped, 1 warning in 13.99s

$ .venv/Scripts/python.exe -m ruff check <all touched files>
All checks passed!

$ .venv/Scripts/python.exe -m mypy <all touched src files>
Success: no issues found
```

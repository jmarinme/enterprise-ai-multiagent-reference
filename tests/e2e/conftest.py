"""Pytest configuration that makes the apps/api FastAPI source importable — same mechanism as
tests/unit/api/conftest.py and tests/conversational/conftest.py.
"""

import sys
from pathlib import Path

_API_SRC = Path(__file__).resolve().parents[2] / "apps" / "api" / "src"
if str(_API_SRC) not in sys.path:
    sys.path.insert(0, str(_API_SRC))

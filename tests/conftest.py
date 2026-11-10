"""Test bootstrap: make the project importable and isolate the database."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TEST_DB = ROOT / "data" / "test-audittrail.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ["ALLOW_DEMO_MODE"] = "true"
os.environ["CLOCKED_API_KEY"] = os.environ.get("CLOCKED_API_KEY", "test-key")
os.environ["STORAGE_BACKEND"] = "sqlite"
# Never let the test suite touch the real Supabase project.
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_SECRET_KEY"] = ""
os.environ["SUPABASE_PUBLISHABLE_KEY"] = ""

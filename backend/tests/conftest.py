"""Shared test setup: every test run uses a throwaway database, never loanlens.db."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="loanlens-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp / 'test.db'}"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["API_KEY"] = "test-api-key"

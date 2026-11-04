"""Test configuration: isolated SQLite DB, repo root on sys.path."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

_tmp = tempfile.mkdtemp(prefix="newstally_test_")
os.environ["NT_DATABASE_URL"] = f"sqlite:///{Path(_tmp, 'test.db').as_posix()}"
os.environ["NT_RATE_LIMIT_PER_MINUTE"] = "1000"
os.environ.setdefault("NT_ENVIRONMENT", "test")

ARTIFACTS = ROOT / "ml" / "artifacts"
HAS_MODELS = (ARTIFACTS / "classifier.joblib").exists() and (ARTIFACTS / "retrieval" / "index_meta.json").exists()
HAS_DATA = (ROOT / "data" / "processed" / "factchecks.csv").exists()

requires_models = pytest.mark.skipif(not (HAS_MODELS and HAS_DATA),
                                     reason="train models + build index first (see README)")


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c

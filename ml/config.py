"""Central path + constant configuration for the ML side of NEWS TALLY.

Every ML module imports paths from here so that scripts, notebooks, the
backend and tests all agree on where data and artifacts live.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.getenv("NT_DATA_DIR", REPO_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
EXTERNAL_DIR = DATA_DIR / "external"
METADATA_DIR = DATA_DIR / "metadata"

ARTIFACTS_DIR = Path(os.getenv("NT_ARTIFACTS_DIR", REPO_ROOT / "ml" / "artifacts"))

PROCESSED_DATASET = PROCESSED_DIR / "factchecks.csv"
PROCESSED_DATASET_JSON = PROCESSED_DIR / "factchecks.jsonl"

RANDOM_SEED = 42

# Polite-crawling defaults (seconds between requests to the same host).
REQUEST_DELAY_SECONDS = float(os.getenv("NT_REQUEST_DELAY", "2.0"))
USER_AGENT = os.getenv(
    "NT_USER_AGENT",
    "Mozilla/5.0 (compatible; NewsTallyResearchBot/0.1; non-commercial student research project)",
)

for _d in (RAW_DIR, PROCESSED_DIR, EXTERNAL_DIR, METADATA_DIR, ARTIFACTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

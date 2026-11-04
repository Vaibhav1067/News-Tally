"""Backend settings, read from environment variables / .env (never hard-coded secrets)."""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
# Make the shared `ml` package importable when uvicorn runs from backend/ or repo root.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(REPO_ROOT / ".env", ".env"), env_prefix="NT_", extra="ignore")

    app_name: str = "NEWS TALLY API"
    environment: str = "development"
    database_url: str = f"sqlite:///{(REPO_ROOT / 'data' / 'news_tally.db').as_posix()}"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # abuse protection
    rate_limit_per_minute: int = 30
    max_request_bytes: int = 64_000
    max_text_chars: int = 10_000

    # URL fetching
    url_fetch_timeout: float = 10.0
    url_max_bytes: int = 3_000_000
    allow_url_fetch: bool = True

    # privacy: submitted text is stored ONLY when the user opts in, and purged after N days
    retention_days: int = 30

    # Retrieval thresholds, read off ml/artifacts/retrieval_eval.json (top-1 precision table):
    # hybrid >= 0.60 -> 95% top-1 precision; >= 0.40 -> 87%.  tfidf >= 0.55 -> 96%; >= 0.35 -> 85%.
    strong_match_threshold: float = 0.60
    related_match_threshold: float = 0.40
    tfidf_strong_match_threshold: float = 0.55
    tfidf_related_match_threshold: float = 0.35

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""Load the processed fact-check dataset into the database.

    python -m app.services.seed          (run from backend/)

Idempotent: existing rows (same id) are updated, new ones inserted.
"""
from __future__ import annotations

import logging
from datetime import date

import pandas as pd
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, init_db
from app.models import FactCheck
from app.services.source_service import seed_sources
from ml.config import PROCESSED_DATASET

log = logging.getLogger(__name__)


def _none(v):
    return None if v is None or (isinstance(v, float) and pd.isna(v)) else v


def _date(v):
    v = _none(v)
    if not v:
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def seed_factchecks(db: Session, path=PROCESSED_DATASET) -> int:
    if not path.exists():
        log.warning("%s not found; nothing to seed", path)
        return 0
    df = pd.read_csv(path)
    existing = {fid for (fid,) in db.query(FactCheck.id)}
    n = 0
    for r in df.to_dict("records"):
        fields = dict(
            claim_text=r["claim_text"], claim_source=_none(r.get("claim_source")),
            title=_none(r.get("fact_check_title")), verdict=_none(r.get("verdict")),
            verdict_raw=(_none(r.get("verdict_raw")) or None) and str(r["verdict_raw"])[:200],
            verdict_rule=_none(r.get("verdict_rule")), explanation=_none(r.get("explanation")),
            source_name=r["publisher"], original_url=r["fact_check_url"], category=_none(r.get("category")),
            category_source=_none(r.get("category_source")), language=_none(r.get("language")),
            publication_date=_date(r.get("publication_date")), collection_date=_none(r.get("collection_date")),
            group_id=int(r["group_id"]) if _none(r.get("group_id")) is not None else None,
        )
        if r["claim_id"] in existing:
            db.query(FactCheck).filter(FactCheck.id == r["claim_id"]).update(fields)
        else:
            db.add(FactCheck(id=r["claim_id"], **fields))
        n += 1
    db.commit()
    return n


def run() -> None:
    logging.basicConfig(level=logging.INFO)
    init_db()
    with SessionLocal() as db:
        n = seed_factchecks(db)
        seed_sources(db)
    log.info("Seeded %d fact-checks and refreshed source evidence", n)


if __name__ == "__main__":
    run()

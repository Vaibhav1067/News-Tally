"""Dataset statistics computed live from the database (never hard-coded)."""
from __future__ import annotations

import json

from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from app.models import Analysis, FactCheck
from ml.config import METADATA_DIR


def _counts(db: Session, col) -> dict:
    rows = db.execute(select(col, func.count()).group_by(col).order_by(func.count().desc())).all()
    missing = {"verdict": "UNPARSED", "category": "Uncategorised"}.get(col.key, "Unknown")
    return {(k if k is not None else missing): v for k, v in rows}


def statistics(db: Session) -> dict:
    total = db.scalar(select(func.count()).select_from(FactCheck)) or 0
    month = func.substr(cast(FactCheck.publication_date, String), 1, 7)
    timeline = db.execute(select(month.label("m"), func.count()).where(FactCheck.publication_date.is_not(None))
                          .group_by("m").order_by("m")).all()
    by_lang_verdict = db.execute(select(FactCheck.language, FactCheck.verdict, func.count())
                                 .group_by(FactCheck.language, FactCheck.verdict)).all()
    lv: dict = {}
    for lang, verdict, c in by_lang_verdict:
        lv.setdefault(lang or "unknown", {})[verdict or "UNPARSED"] = c
    dates = db.execute(select(func.min(FactCheck.publication_date), func.max(FactCheck.publication_date))).one()
    categories = _counts(db, FactCheck.category)
    report_path = METADATA_DIR / "dataset_report.json"
    quality = {}
    if report_path.exists():
        rep = json.loads(report_path.read_text(encoding="utf-8"))
        quality = {k: rep.get(k) for k in ("raw_rows", "final_rows", "duplicate_pct", "duplicate_urls",
                                           "duplicate_claim_texts", "near_duplicate_rows", "invalid_rows",
                                           "missing_pct_processed", "built_at", "claim_source_distribution",
                                           "category_source_distribution")}
    return {
        "total_fact_checks": total,
        "verdict_distribution": _counts(db, FactCheck.verdict),
        "language_distribution": _counts(db, FactCheck.language),
        "source_distribution": _counts(db, FactCheck.source_name),
        "category_distribution": dict(list(categories.items())[:12]),
        "timeline": [{"month": m, "count": c} for m, c in timeline if m],
        "language_by_verdict": lv,
        "date_range": [str(dates[0]) if dates[0] else None, str(dates[1]) if dates[1] else None],
        "analyses_run": db.scalar(select(func.count()).select_from(Analysis)) or 0,
        "data_quality": quality,
        "note": ("These statistics describe the collected fact-check dataset. They reflect what Factly and Alt News "
                 "chose to fact-check, not the prevalence of misinformation in India."),
    }

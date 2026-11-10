"""HTTP routes. Thin layer: validate -> call a service -> shape the response."""
from __future__ import annotations

import json
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models import Analysis, FactCheck, Feedback
from app.schemas import (AnalyzeRequest, AnalyzeResponse, FactCheckOut, FactCheckPage, FeedbackIn, FeedbackOut,
                         HistoryItem)
from app.services import ml_registry, pipeline
from app.services.extraction import ExtractionError
from app.services.geo_service import india_map
from app.services.stats_service import statistics
from ml.config import ARTIFACTS_DIR

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


@router.get("/health", tags=["meta"])
def health(db: Session = Depends(get_db)) -> dict:
    n = db.scalar(select(func.count()).select_from(FactCheck)) or 0
    status = ml_registry.get_registry().status()
    return {"status": "ok", "fact_checks_loaded": n, "components": status,
            "environment": get_settings().environment}


@router.post("/analyze", response_model=AnalyzeResponse, tags=["analysis"])
def analyze(req: AnalyzeRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return pipeline.analyze(db, req.text, str(req.url) if req.url else None, req.language, req.save_to_history)
    except ExtractionError as exc:
        raise HTTPException(status_code=422, detail=f"Could not extract content from the URL: {exc}")


@router.get("/statistics", tags=["dataset"])
def get_statistics(db: Session = Depends(get_db)) -> dict:
    return statistics(db)


@router.get("/map", tags=["dataset"])
def get_map(db: Session = Depends(get_db)) -> dict:
    """NCRB 2023 crime rate per state, joined with the fact-checks in this dataset that name the state."""
    return india_map(db)


@router.get("/fact-checks", response_model=FactCheckPage, tags=["dataset"])
def list_fact_checks(
    db: Session = Depends(get_db),
    q: Optional[str] = Query(None, max_length=200, description="Search claim, headline and explanation"),
    language: Optional[str] = Query(None, max_length=12),
    verdict: Optional[str] = Query(None, max_length=32, description="Verdict, or UNPARSED"),
    source: Optional[str] = Query(None, max_length=100),
    category: Optional[str] = Query(None, max_length=100),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    stmt = select(FactCheck)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(FactCheck.claim_text.ilike(like), FactCheck.title.ilike(like),
                              FactCheck.explanation.ilike(like)))
    if language:
        stmt = stmt.where(FactCheck.language == language)
    if verdict:
        stmt = stmt.where(FactCheck.verdict.is_(None) if verdict == "UNPARSED" else FactCheck.verdict == verdict)
    if source:
        stmt = stmt.where(FactCheck.source_name == source)
    if category:
        stmt = stmt.where(FactCheck.category == category)
    if date_from:
        stmt = stmt.where(FactCheck.publication_date >= date_from)
    if date_to:
        stmt = stmt.where(FactCheck.publication_date <= date_to)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(FactCheck.publication_date.desc().nulls_last(), FactCheck.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


@router.get("/fact-checks/facets", tags=["dataset"])
def facets(db: Session = Depends(get_db)) -> dict:
    def distinct(col):
        return [v for (v,) in db.execute(select(col).where(col.is_not(None)).distinct().order_by(col))]
    return {"languages": distinct(FactCheck.language), "verdicts": distinct(FactCheck.verdict) + ["UNPARSED"],
            "sources": distinct(FactCheck.source_name), "categories": distinct(FactCheck.category)}


@router.get("/fact-checks/{fact_check_id}", response_model=FactCheckOut, tags=["dataset"])
def get_fact_check(fact_check_id: str, db: Session = Depends(get_db)):
    fc = db.get(FactCheck, fact_check_id)
    if not fc:
        raise HTTPException(status_code=404, detail="Fact-check not found")
    return fc


@router.get("/models", tags=["meta"])
def models() -> dict:
    reg = ml_registry.get_registry()
    meta = reg.classifier_meta or {}
    retrieval_eval = ARTIFACTS_DIR / "retrieval_eval.json"
    transformer = ARTIFACTS_DIR / "transformer" / "transformer_metrics.json"
    return {
        "components": reg.status(),
        "classifier": {k: meta.get(k) for k in ("deployed_model", "best_validation_model", "classes", "task",
                                                 "n_train", "n_val", "n_test", "split", "features", "trained_at",
                                                 "label_distribution_train", "deployed_breakdown_test")},
        "comparison": {name: {"validation_macro_f1": r["validation"]["f1_macro"], "test_macro_f1": r["test"]["f1_macro"],
                              "test_accuracy": r["test"]["accuracy"], "test_weighted_f1": r["test"]["f1_weighted"],
                              "test_ece": r["test"].get("calibration", {}).get("ece")}
                       for name, r in (meta.get("results") or {}).items()},
        "deployed_test_metrics": (meta.get("results") or {}).get(meta.get("deployed_model"), {}).get("test"),
        "retrieval_evaluation": json.loads(retrieval_eval.read_text()) if retrieval_eval.exists() else None,
        "transformer_experiment": json.loads(transformer.read_text()) if transformer.exists() else None,
    }


@router.get("/history", response_model=list[HistoryItem], tags=["analysis"])
def history(db: Session = Depends(get_db), limit: int = Query(20, ge=1, le=100)):
    """Only analyses the user explicitly chose to save are listed."""
    pipeline.purge_expired(db)
    return db.scalars(select(Analysis).where(Analysis.stored_with_consent.is_(True))
                      .order_by(Analysis.created_at.desc()).limit(limit)).all()


@router.post("/feedback", response_model=FeedbackOut, status_code=201, tags=["analysis"])
def feedback(body: FeedbackIn, db: Session = Depends(get_db)):
    if not db.get(Analysis, body.analysis_id):
        raise HTTPException(status_code=404, detail="Analysis not found")
    fb = Feedback(analysis_id=body.analysis_id, feedback_type=body.feedback_type, comments=body.comments)
    db.add(fb)
    db.commit()
    return FeedbackOut(id=fb.id, analysis_id=fb.analysis_id, feedback_type=fb.feedback_type, created_at=fb.created_at)

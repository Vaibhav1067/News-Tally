"""The analysis pipeline: one function per stage, orchestrated by ``analyze``.

    input validation -> content extraction -> language detection -> preprocessing
    -> fact-check retrieval -> ML classification -> source analysis
    -> explainability -> risk assessment -> result
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Analysis, FactCheck
from app.services import ml_registry
from app.services.extraction import ExtractionError, fetch_url
from app.services.risk_engine import MatchInput, RiskInput, assess
from app.services.source_service import source_info
from ml.preprocessing.language import SUPPORTED_FOR_MODEL, detect_language
from ml.preprocessing.text_cleaning import clean_text, extract_urls, model_text, truncate

log = logging.getLogger(__name__)

DISCLAIMER = ("NEWS TALLY is an information-assistance tool. It surfaces published fact-checks and model signals; "
              "it does not determine truth. Always read the original fact-check before sharing conclusions.")
MIN_WORDS_FOR_MODEL = 4
MAX_MODEL_CHARS = 5000


# ---- stages ------------------------------------------------------------------
def extract_content(text: Optional[str], url: Optional[str]) -> dict:
    s = get_settings()
    out = {"text": "", "source": "text", "url": url, "title": None, "truncated": False,
           "extraction_error": None}
    if url:
        try:
            ex = fetch_url(url)
            out.update(title=ex.title, url=ex.final_url)
            out["text"] = f"{text}\n\n{ex.text}" if text else ex.text
            out["source"] = "text+url" if text else "url"
        except ExtractionError as exc:
            out["extraction_error"] = str(exc)
            if not text:
                raise
            out["text"] = text
    else:
        out["text"] = text or ""
    cleaned = clean_text(out["text"])
    if len(cleaned) > s.max_text_chars:
        cleaned, out["truncated"] = cleaned[: s.max_text_chars], True
    out["text"] = cleaned
    out["char_count"] = len(cleaned)
    out["urls_in_text"] = extract_urls(text or "")[:10]
    return out


def retrieval_query(content: dict) -> str:
    # Titles of articles are often the claim; prefer title + opening text.
    base = content["text"][:1000]
    return f"{content['title']}. {base}" if content.get("title") else base


def retrieve(db: Session, query: str, k: int = 5) -> tuple[list[dict], str]:
    reg = ml_registry.get_registry()
    if reg.index is None:
        return [], "unavailable"
    strong_t, related_t = thresholds(reg.index.backend)
    hits = reg.index.search(query, k=k)
    rows = {fc.id: fc for fc in db.scalars(select(FactCheck).where(FactCheck.id.in_([h.claim_id for h in hits])))}
    today = date.today()
    matches = []
    for h in hits:
        fc = rows.get(h.claim_id)
        if not fc:
            continue
        strength = "strong" if h.similarity >= strong_t else "related" if h.similarity >= related_t else "weak"
        matches.append({
            "id": fc.id, "claim_text": fc.claim_text, "title": fc.title, "verdict": fc.verdict,
            "explanation": fc.explanation, "source_name": fc.source_name, "original_url": fc.original_url,
            "language": fc.language, "publication_date": fc.publication_date, "similarity": h.similarity,
            "match_strength": strength,
            "age_days": (today - fc.publication_date).days if fc.publication_date else None,
        })
    return matches, reg.index.backend


def thresholds(backend: str) -> tuple[float, float]:
    s = get_settings()
    if backend == "hybrid":
        return s.strong_match_threshold, s.related_match_threshold
    return s.tfidf_strong_match_threshold, s.tfidf_related_match_threshold


def classify(text_for_model: str, lang_code: str, n_words: int) -> dict:
    reg = ml_registry.get_registry()
    in_domain = lang_code in SUPPORTED_FOR_MODEL or lang_code == "mixed"
    if reg.classifier is None:
        return {"available": False, "in_domain": False,
                "note": reg.errors.get("classifier", "Classifier unavailable.")}
    proba = reg.classifier.predict_proba([text_for_model])[0]
    probs = {c: round(float(p), 4) for c, p in zip(reg.classifier.classes_, proba)}
    label = max(probs, key=probs.get)
    notes = ["Trained only on claims that fact-checkers chose to investigate; it estimates which verdict "
             "category similar claims received, not whether this text is true."]
    if not in_domain:
        notes.append(f"Language '{lang_code}' was not in the training data; output is not reliable.")
    if n_words < MIN_WORDS_FOR_MODEL:
        in_domain = False
        notes.append("Text is too short for a meaningful prediction.")
    return {"available": True, "label": label, "probabilities": probs, "confidence": probs[label],
            "model_name": reg.classifier_meta.get("deployed_model"), "in_domain": in_domain,
            "note": " ".join(notes)}


def explain(text_for_model: str, label: Optional[str]) -> dict:
    reg = ml_registry.get_registry()
    if reg.explainer is None:
        return {"available": False, "reason": "No classifier is loaded, so there is nothing to explain."}
    return reg.explainer.explain(text_for_model, target_class=label)


# ---- orchestration -------------------------------------------------------------
def analyze(db: Session, text: Optional[str], url: Optional[str], language_hint: Optional[str],
            save_to_history: bool) -> dict:
    t0 = time.perf_counter()
    content = extract_content(text, url)
    lang = detect_language(content["text"]).to_dict()
    lang["user_hint"] = language_hint
    lang_code = language_hint if language_hint in SUPPORTED_FOR_MODEL else lang["code"]

    mt = model_text(content["text"][:MAX_MODEL_CHARS])
    n_words = len(mt.split())
    matches, backend = retrieve(db, retrieval_query(content))
    prediction = classify(mt, lang_code, n_words)
    src = source_info(db, content.get("url"))
    explanation = explain(mt, prediction.get("label")) if prediction.get("available") else {
        "available": False, "reason": prediction.get("note")}

    strong_t, related_t = thresholds(backend)
    risk = assess(RiskInput(
        matches=[MatchInput(m["verdict"], m["similarity"], m["age_days"], m["title"] or m["claim_text"],
                            m["source_name"]) for m in matches],
        strong_threshold=strong_t, related_threshold=related_t,
        class_probabilities=prediction.get("probabilities", {}) if prediction.get("available") else {},
        classifier_in_domain=bool(prediction.get("in_domain")),
        text_too_short=n_words < MIN_WORDS_FOR_MODEL,
        source_is_fact_checker=src.get("status") == "fact_checker",
        source_known=src.get("status") in ("fact_checker", "known_source"),
        source_name=src.get("name"),
    ))
    if backend == "unavailable":
        risk.missing_evidence.insert(0, "The fact-check retrieval index is not built, so no evidence could be searched.")

    elapsed = int((time.perf_counter() - t0) * 1000)
    analysis_id = str(uuid.uuid4())
    top = matches[0] if matches else None
    db.add(Analysis(
        id=analysis_id,
        submitted_text=content["text"] if save_to_history else None,
        text_preview=truncate(content["text"], 150) if save_to_history else None,
        submitted_url=content.get("url") if save_to_history else None,
        stored_with_consent=save_to_history,
        detected_language=lang["code"], predicted_class=prediction.get("label"),
        confidence=prediction.get("confidence"), risk_level=risk.level, risk_score=risk.risk_score,
        evidence_strength=risk.evidence_strength, top_match_id=top["id"] if top else None,
        top_match_similarity=top["similarity"] if top else None, processing_ms=elapsed,
    ))
    db.commit()

    return {
        "analysis_id": analysis_id,
        "detected_language": lang,
        "extracted_content": content,
        "prediction": prediction,
        "confidence": prediction.get("confidence"),
        "risk_assessment": risk.__dict__,
        "matching_fact_checks": matches,
        "source_information": src,
        "explanation": explanation,
        "retrieval_backend": backend,
        "processing_time_ms": elapsed,
        "stored": save_to_history,
        "disclaimer": DISCLAIMER,
    }


def purge_expired(db: Session) -> int:
    """Delete stored submission text older than the retention window (metadata rows stay)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=get_settings().retention_days)
    rows = list(db.scalars(select(Analysis).where(Analysis.stored_with_consent.is_(True),
                                                  Analysis.created_at < cutoff)))
    for r in rows:
        r.submitted_text = r.text_preview = r.submitted_url = None
        r.stored_with_consent = False
    db.commit()
    return len(rows)


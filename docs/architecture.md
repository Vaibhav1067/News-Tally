# Architecture

NEWS TALLY is a monorepo with three code bases that share one Python package:

```
frontend/  React + TypeScript + Vite + Tailwind  ──HTTP /api──►  backend/  FastAPI + SQLAlchemy
                                                                     │ imports
                                                                     ▼
                                                     ml/  data collection, preprocessing, training,
                                                          retrieval, explainability (pure Python)
```

`ml/` never imports `backend/`. The backend imports `ml/` so that **the exact same cleaning,
language detection and feature code runs at training time and at request time** (no
training/serving skew).

## Request pipeline (`POST /api/analyze`)

Each stage is a separate function in `backend/app/services/pipeline.py`, backed by its own module:

| Stage | Module | Output |
|---|---|---|
| Input validation | `app/schemas` (Pydantic) + `app/core/middleware.py` | 422 / 413 / 429 on bad input |
| Content extraction | `app/services/extraction.py` | text (+ title) from text or URL; SSRF-guarded |
| Language detection | `ml/preprocessing/language.py` | code, confidence, mixed flag, model support |
| Preprocessing | `ml/preprocessing/text_cleaning.py` | cleaned text, model text |
| Fact-check retrieval | `ml/retrieval/index.py` | top-5 fact-checks with hybrid similarity |
| ML classification | `app/services/pipeline.classify` + `ml/artifacts/classifier.joblib` | verdict-type probabilities |
| Source analysis | `app/services/source_service.py` | domain profile from dataset mentions |
| Explainability | `ml/explainability/explain.py` | exact linear SHAP values + token highlights |
| Risk assessment | `app/services/risk_engine.py` (pure function) | label, risk index, evidence strength, reasons |
| Result generation | `app/schemas.AnalyzeResponse` | one JSON document |

Typical latency on a laptop CPU: 40–120 ms per request after start-up (the embedding model
loads once at start-up, ~3 s).

## Offline pipeline

```
run_collection ──► data/raw/*.jsonl ──► build_dataset ──► data/processed/factchecks.csv
                                                    │            + data/metadata/dataset_report.json
                                                    ├──► train_classical ──► ml/artifacts/classifier.joblib (+ metadata, comparison)
                                                    ├──► retrieval.index ──► ml/artifacts/retrieval/
                                                    ├──► retrieval_eval  ──► ml/artifacts/retrieval_eval.json
                                                    ├──► train_transformer (optional) ──► ml/artifacts/transformer/
                                                    └──► app.services.seed ──► database (FactCheck, Source)
```

`python scripts/run_pipeline.py` runs these in order.

## Data model

| Table | Purpose | Key columns |
|---|---|---|
| `fact_checks` | Collected fact-checks | id (= claim_id), claim_text, title, verdict (nullable), verdict_rule, source_name, original_url (unique), language, category, publication_date, group_id |
| `sources` | Directory of outlets/fact-checkers (no ratings) | domain (unique), name, source_type, aliases, available_fact_checks, evidence_summary |
| `analyses` | One row per analysis | id, detected_language, predicted_class, confidence, risk_level, risk_score, evidence_strength; `submitted_text` only with consent |
| `feedback` | User feedback | analysis_id → analyses.id (cascade), feedback_type, comments |

Indexes: verdict, language, source_name, category, publication_date, (language, verdict);
analyses.created_at, risk_level; feedback.analysis_id.

## Operational concerns

* **Rate limiting**: in-memory sliding window per IP on POST endpoints. Correct for one instance; for
  several instances move the counter to Redis.
* **Request size**: `Content-Length` limit (64 KB) + Pydantic `max_length` on text.
* **Privacy**: submitted text is stored only when `save_to_history=true`; `purge_expired` clears it
  after `NT_RETENTION_DAYS`. Request bodies are never logged.
* **Graceful degradation**: missing artifacts do not crash the API; `/api/health` and every response
  say which component is unavailable, and no substitute predictions are produced.
* **Memory**: the dense embedding model needs ~500 MB RAM. On small hosts set
  `NT_DISABLE_EMBEDDINGS=1` to fall back to lexical retrieval (R@1 0.819 vs 0.845).

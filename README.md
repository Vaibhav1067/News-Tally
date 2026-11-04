# NEWS TALLY

**Understand the claim. Examine the evidence.**

An India-focused misinformation intelligence platform. Paste a claim, a WhatsApp-style forward, a
post or a news URL — in English, Hindi, Kannada or mixed — and NEWS TALLY:

1. finds the most similar **published Indian fact-checks** (Factly, Alt News) and links to them;
2. reports which verdict a **TF-IDF classifier** associates with text like this, with calibration checked;
3. profiles the **source** domain from what the dataset actually records (no invented credibility scores);
4. explains the model with **exact SHAP values**;
5. combines everything in a **documented, rule-gated risk assessment** that separates risk from
   evidence strength and lists the evidence that is missing.

It is an information-assistance tool, not an automated truth oracle: a classifier alone can never
label a claim "high risk".

---

## What is real in this repository

| Component | Status | Evidence |
|---|---|---|
| Data ingestion (Factly EN/KN, Alt News EN/HI) | working | 4,138 raw → 4,137 processed records; `data/metadata/collection_log.jsonl` |
| BOOM Live, PIB Fact Check | **not collected** — they refused access (403/401) | `docs/data_sources.md` |
| Cleaning, validation, dedup, near-dup grouping, EDA | working | `data/metadata/dataset_report.json`, notebooks 02–03 |
| Classical ML (NB, LR, SVM + dummy baselines) | trained & evaluated | `ml/artifacts/model_comparison.md` |
| Multilingual transformer experiment | run on CPU, documented | `ml/artifacts/transformer/transformer_metrics.json`, notebook 06 |
| Hybrid semantic retrieval | working, evaluated (R@1 0.845) | `ml/artifacts/retrieval_eval.json` |
| Source evidence engine | working (mention-based, no scores) | `backend/app/services/source_service.py` |
| Risk engine | working, unit-tested | `backend/app/services/risk_engine.py` |
| SHAP explainability | working, verified against `shap` | `backend/tests/test_models.py` |
| FastAPI backend (9 endpoints) | working | `/docs` |
| React frontend (5 pages) | working against the live API | `frontend/` |
| Tests | 82 passing | `pytest` |
| Deployment configs (Docker, Render, Vercel) | written, **not deployed** | `docker-compose.yml`, `render.yaml`, `frontend/vercel.json` |

Headline numbers (all computed by the scripts; nothing typed in by hand):

* Classifier (Logistic Regression, 3 classes): **test macro-F1 0.527** vs 0.305 for a stratified
  random baseline; ECE 0.125. A fine-tuned multilingual MiniLM reached 0.560 on the same split (kept
  as an experiment; see `docs/model_card.md` for why it is not deployed yet).
* Retrieval (hybrid): **recall@1 0.845, recall@5 0.933**; top-1 precision 0.95 at the "strong match" threshold.
* Verdict labels come from rules with an estimated ~85–92% precision (`data/metadata/verdict_audit.md`).

---

## Quick start (Windows, macOS, Linux)

Requirements: Python 3.11+ (tested 3.12), Node 20+ (tested 25), ~3 GB free disk.

```bash
# 1. Python environment (CPU-only torch keeps it laptop-sized)
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-dev.txt

# 2. Build everything from the included raw data (≈2 minutes; downloads a 470 MB embedding model once)
python scripts/run_pipeline.py
#    ...or re-collect fresh data first (≈6 minutes of polite crawling):
#    python scripts/run_pipeline.py --collect 25

# 3. API  →  http://127.0.0.1:8000/docs
uvicorn app.main:app --app-dir backend --port 8000

# 4. Frontend  →  http://localhost:5173   (in a second terminal)
cd frontend
npm install
npm run dev

# 5. Tests
pytest
```

On first start the API creates the SQLite database (`data/news_tally.db`) and seeds it from
`data/processed/factchecks.csv`. To use PostgreSQL set `NT_DATABASE_URL` (see `.env.example`) or run
`docker compose up --build`.

Optional: `python -m ml.training.train_transformer` (~10 min on CPU, ~470 MB checkpoint).

---

## Repository layout

```
news-tally/
├── frontend/            React + TS + Vite + Tailwind v4 + Framer Motion + Recharts + Lucide
│   └── src/{components,pages,hooks,services,types,utils}
├── backend/
│   ├── app/{api,core,models,schemas,services}, main.py
│   └── tests/           unit, API integration, model, edge-case tests
├── ml/
│   ├── data_collection/ polite HTTP, sources, WordPress collector, verdict rules, importer
│   ├── preprocessing/   cleaning, language ID, dedup, validation, dataset build
│   ├── training/        features, group splits, classical + transformer training
│   ├── evaluation/      metrics (macro-F1, ECE), retrieval evaluation
│   ├── explainability/  exact linear SHAP
│   ├── retrieval/       hybrid dense + lexical index
│   └── artifacts/       trained models, reports
├── notebooks/           01–08 research notebooks (executed)
├── data/{raw,processed,external,metadata}
├── docs/                architecture, methodology, data sources, model card
└── scripts/             run_pipeline.py, make_notebooks.py
```

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/analyze` | `{text?, url?, language?, save_to_history?}` → full analysis |
| GET | `/api/health` | status + which components are loaded |
| GET | `/api/statistics` | live dataset statistics |
| GET | `/api/fact-checks` | search + filters (`q, language, verdict, source, category, date_from, date_to, page`) |
| GET | `/api/fact-checks/facets` | filter values |
| GET | `/api/fact-checks/{id}` | one record |
| GET | `/api/models` | model comparison, retrieval and transformer evaluations |
| GET | `/api/history` | analyses the user opted to save |
| POST | `/api/feedback` | `{analysis_id, feedback_type, comments?}` |

Protections: Pydantic validation, 64 KB body limit, 10k-character text limit, 30 req/min/IP on
POSTs, SSRF guard on URL fetching, opt-in storage with a 30-day purge.

## Documentation

* [docs/architecture.md](docs/architecture.md) — modules, request pipeline, data model, operations
* [docs/methodology.md](docs/methodology.md) — NLP, models, retrieval, risk formula, safeguards
* [docs/data_sources.md](docs/data_sources.md) — what was collected, how, and what was refused
* [docs/model_card.md](docs/model_card.md) — intended use, metrics, limitations
* [docs/roadmap.md](docs/roadmap.md) — phases, what is done, what is next

## Ethics

Collected only through public APIs allowed by robots.txt, with an honest User-Agent and 2 s
between requests; refusals were respected. Only headlines, claims and one-sentence conclusions are
stored, each linked to the publisher's article. Statistics describe this collection, not the
prevalence of misinformation in India.

"""Evaluate the retrieval index and derive similarity thresholds from data.

    python -m ml.evaluation.retrieval_eval

Setup (no leakage between query and document):
* documents = fact-check HEADLINES (exactly what the deployed index stores)
* queries   = the circulating claim from Factly's "Claim:" block — worded by
  the claimant, not the fact-checker
* the correct answer for a query is its own article

Reports Recall@1/5/10, MRR, per-language recall, and top-1 precision at
several score thresholds. The API's "strong"/"related" thresholds are taken
from this table (see backend/app/core/config.py and docs/methodology.md).
"""
from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd

from ml.config import ARTIFACTS_DIR, PROCESSED_DATASET
from ml.retrieval.index import FactCheckIndex

log = logging.getLogger("retrieval_eval")
THRESHOLDS = [0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.8]


def evaluate(use_dense: bool, max_queries: int = 1500) -> dict:
    df = pd.read_csv(PROCESSED_DATASET)
    idx = FactCheckIndex.build(df, use_dense=use_dense)
    q = df[(df["claim_source"] == "claim_field") & (df["claim_text"] != df["fact_check_title"])]
    q = q.sample(min(max_queries, len(q)), random_state=0)
    pos = {cid: i for i, cid in enumerate(idx.ids)}
    ranks, top1_sim, correct = [], [], []
    for cid, text in zip(q["claim_id"], q["claim_text"]):
        s, _, _ = idx.scores(text)
        t = pos[cid]
        ranks.append(int((s > s[t]).sum()) + 1)
        top1_sim.append(float(s.max()))
        correct.append(int(s.argmax() == t))
    ranks, top1_sim, correct = np.array(ranks), np.array(top1_sim), np.array(correct)
    out = {
        "backend": idx.backend, "n_queries": int(len(q)), "n_documents": len(idx.ids),
        "recall@1": round(float((ranks <= 1).mean()), 4), "recall@5": round(float((ranks <= 5).mean()), 4),
        "recall@10": round(float((ranks <= 10).mean()), 4), "mrr": round(float((1 / ranks).mean()), 4),
        "precision_at_threshold": {}, "by_language": {},
    }
    for th in THRESHOLDS:
        m = top1_sim >= th
        if m.sum():
            out["precision_at_threshold"][str(th)] = {"top1_precision": round(float(correct[m].mean()), 4),
                                                      "coverage": round(float(m.mean()), 4)}
    for lang in sorted(q["language"].unique()):
        m = (q["language"] == lang).to_numpy()
        out["by_language"][lang] = {"n": int(m.sum()), "recall@1": round(float((ranks[m] <= 1).mean()), 4),
                                    "recall@5": round(float((ranks[m] <= 5).mean()), 4)}
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for noisy in ("httpx", "huggingface_hub", "sentence_transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    results = {"hybrid": evaluate(use_dense=True), "tfidf_char": evaluate(use_dense=False),
               "note": "Queries = Factly 'Claim:' texts (en, kn); no Hindi queries exist, so cross-lingual "
                       "and Hindi retrieval quality is NOT measured here."}
    (ARTIFACTS_DIR / "retrieval_eval.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

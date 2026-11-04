"""Stage C — semantic fact-check retrieval (hybrid dense + lexical).

    python -m ml.retrieval.index                      # build
    python -m ml.retrieval.index --query "..."        # try it

Design, chosen from measurements in ml/evaluation/retrieval_eval.py
(headline documents, Factly "Claim:" texts as queries, n=1500):

| method                                   | R@1   | R@5   | Kannada R@1 |
|------------------------------------------|-------|-------|-------------|
| dense MiniLM-multilingual only           | 0.557 | 0.647 | 0.073       |
| char 2-5gram TF-IDF only                 | 0.819 | 0.921 | 0.819       |
| hybrid 0.5/0.5, Kannada-aware (deployed) | 0.845 | 0.933 | 0.819       |

* The dense encoder (paraphrase-multilingual-MiniLM-L12-v2) gives cross-lingual
  matching (Hindi query -> English fact-check) but was not trained on Kannada,
  whose texts collapse to near-identical vectors. So whenever the query or the
  document is Kannada we use the lexical score alone.
* Char n-gram TF-IDF is script-agnostic and robust to spelling variants.

score = 0.5·cos_dense + 0.5·cos_tfidf   (cos_tfidf only, if Kannada is involved)

The score is a RETRIEVAL RELEVANCE measure, never evidence that a new claim
shares the matched verdict.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from ml.config import ARTIFACTS_DIR, PROCESSED_DATASET
from ml.preprocessing.language import script_profile
from ml.preprocessing.text_cleaning import clean_text

log = logging.getLogger(__name__)

MODEL_NAME = os.getenv("NT_EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
INDEX_DIR = ARTIFACTS_DIR / "retrieval"
ALPHA = 0.5  # weight of the dense score in the hybrid
DENSE_UNSUPPORTED = {"kn"}  # languages the dense encoder handles badly (measured)


def document_text(row) -> str:
    return clean_text(str(row.get("fact_check_title") or row.get("claim_text") or ""))


def dominant_script_lang(text: str) -> str:
    prof = script_profile(text)
    return max(prof, key=prof.get) if prof else "unknown"


def load_dense_model():
    if os.getenv("NT_DISABLE_EMBEDDINGS") == "1":
        return None
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(MODEL_NAME, device="cpu")
    except Exception as exc:
        log.warning("Dense encoder unavailable (%s); lexical-only retrieval", exc)
        return None


def build_tfidf(texts: list[str]) -> TfidfVectorizer:
    return TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=2, sublinear_tf=True,
                           max_features=100000).fit(texts)


@dataclass
class SearchHit:
    claim_id: str
    similarity: float
    rank: int
    dense: Optional[float] = None
    lexical: Optional[float] = None


class FactCheckIndex:
    def __init__(self, ids: list[str], doc_langs: list[str], tfidf: TfidfVectorizer, lex_matrix,
                 dense_model=None, dense_matrix: Optional[np.ndarray] = None):
        self.ids, self.doc_langs = ids, np.array(doc_langs)
        self.tfidf, self.lex = tfidf, lex_matrix
        self.dense_model, self.dense = dense_model, dense_matrix
        self._dense_ok = ~np.isin(self.doc_langs, list(DENSE_UNSUPPORTED))

    @property
    def backend(self) -> str:
        return "hybrid" if self.dense_model is not None and self.dense is not None else "tfidf_char"

    def scores(self, query: str) -> tuple[np.ndarray, Optional[np.ndarray], np.ndarray]:
        q = clean_text(query)
        lex = np.asarray((self.tfidf.transform([q]) @ self.lex.T).todense()).ravel()
        if self.backend != "hybrid":
            return lex, None, lex
        dense = (self.dense @ self.dense_model.encode([q], normalize_embeddings=True)[0]).astype(float)
        if dominant_script_lang(q) in DENSE_UNSUPPORTED:
            return lex, dense, lex
        combined = np.where(self._dense_ok, ALPHA * dense + (1 - ALPHA) * lex, lex)
        return combined, dense, lex

    def search(self, query: str, k: int = 5, min_similarity: float = 0.0) -> list[SearchHit]:
        combined, dense, lex = self.scores(query)
        top = np.argsort(-combined)[:k]
        return [SearchHit(self.ids[i], round(float(combined[i]), 4), r + 1,
                          None if dense is None else round(float(dense[i]), 4), round(float(lex[i]), 4))
                for r, i in enumerate(top) if combined[i] >= min_similarity]

    # ---- build / persist ------------------------------------------------------------
    @classmethod
    def build(cls, df: pd.DataFrame, use_dense: bool = True) -> "FactCheckIndex":
        texts = [document_text(r) for _, r in df.iterrows()]
        tfidf = build_tfidf(texts)
        lex = tfidf.transform(texts)
        model = load_dense_model() if use_dense else None
        dense = (model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
                 .astype(np.float32) if model is not None else None)
        return cls(df["claim_id"].tolist(), df["language"].fillna("unknown").tolist(), tfidf, lex, model, dense)

    def save(self) -> None:
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        for old in INDEX_DIR.glob("*"):
            old.unlink()
        joblib.dump(self.tfidf, INDEX_DIR / "tfidf_vectorizer.joblib")
        joblib.dump(self.lex, INDEX_DIR / "tfidf_matrix.joblib")
        if self.dense is not None:
            np.save(INDEX_DIR / "dense_embeddings.npy", self.dense)
        (INDEX_DIR / "index_meta.json").write_text(json.dumps({
            "backend": self.backend, "dense_model": MODEL_NAME if self.dense is not None else None,
            "alpha": ALPHA, "dense_unsupported_languages": sorted(DENSE_UNSUPPORTED),
            "n": len(self.ids), "ids": self.ids, "doc_langs": self.doc_langs.tolist()}, ensure_ascii=False),
            encoding="utf-8")

    @classmethod
    def load(cls) -> "FactCheckIndex":
        meta_path = INDEX_DIR / "index_meta.json"
        if not meta_path.exists():
            raise FileNotFoundError(meta_path)
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        tfidf = joblib.load(INDEX_DIR / "tfidf_vectorizer.joblib")
        lex = joblib.load(INDEX_DIR / "tfidf_matrix.joblib")
        dense_path = INDEX_DIR / "dense_embeddings.npy"
        model = load_dense_model() if dense_path.exists() else None
        dense = np.load(dense_path) if (dense_path.exists() and model is not None) else None
        return cls(meta["ids"], meta["doc_langs"], tfidf, lex, model, dense)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for noisy in ("httpx", "huggingface_hub", "sentence_transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    ap = argparse.ArgumentParser()
    ap.add_argument("--lexical-only", action="store_true")
    ap.add_argument("--query")
    args = ap.parse_args()
    df = pd.read_csv(PROCESSED_DATASET)
    if args.query:
        idx = FactCheckIndex.load()
        lookup = df.set_index("claim_id")
        for h in idx.search(args.query, k=5):
            r = lookup.loc[h.claim_id]
            print(f"{h.rank}. score={h.similarity:.3f} (dense={h.dense}, lexical={h.lexical}) [{r['verdict']}] "
                  f"{r['fact_check_title']}\n   {r['fact_check_url']}")
        return
    idx = FactCheckIndex.build(df, use_dense=not args.lexical_only)
    idx.save()
    log.info("Built %s index over %d fact-checks -> %s", idx.backend, len(idx.ids), INDEX_DIR)


if __name__ == "__main__":
    main()

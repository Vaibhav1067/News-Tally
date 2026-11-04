"""Duplicate and near-duplicate detection.

Two different problems:

1. **Exact duplicates** — the same article collected twice (same URL), or the
   same claim text. These are simply dropped.
2. **Near-duplicates** — the *same viral claim* debunked again months later or
   by another publisher ("Video of X shared as Y" vs "Old video of X shared as
   Y"). These are legitimate separate records, but if one lands in the
   training set and its twin in the test set, the test score is inflated.
   This is the most common form of data leakage in fact-check datasets.

We give near-duplicates a shared ``group_id`` so the splitter can keep a whole
group on one side of the train/test boundary.

Method: character 3–5-gram TF-IDF (works for any script, robust to small
edits) + cosine similarity, then union-find to merge pairs into groups.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors

from ml.preprocessing.text_cleaning import model_text


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def drop_exact_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    before = len(df)
    df = df.drop_duplicates(subset="fact_check_url", keep="last")
    by_url = before - len(df)
    key = df["claim_text"].map(model_text)
    mask = key.duplicated(keep="first")
    df = df[~mask]
    return df.reset_index(drop=True), {"duplicate_urls": int(by_url), "duplicate_claim_texts": int(mask.sum())}


def near_duplicate_groups(texts: list[str], threshold: float = 0.8) -> np.ndarray:
    """Return an int group id per text; texts with cosine >= threshold share a group."""
    n = len(texts)
    if n == 0:
        return np.array([], dtype=int)
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1, sublinear_tf=True)
    X = vec.fit_transform([model_text(t) for t in texts])
    nn = NearestNeighbors(n_neighbors=min(10, n), metric="cosine").fit(X)
    dist, idx = nn.kneighbors(X)
    uf = _UnionFind(n)
    for i in range(n):
        for d, j in zip(dist[i], idx[i]):
            if j != i and (1 - d) >= threshold:
                uf.union(i, int(j))
    roots = np.array([uf.find(i) for i in range(n)])
    # relabel to 0..k-1
    _, group_ids = np.unique(roots, return_inverse=True)
    return group_ids

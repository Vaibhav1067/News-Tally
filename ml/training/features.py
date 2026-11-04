"""Feature extraction + training-set preparation for classical models.

Features = word 1–2-grams  +  character 2–5-grams (``char_wb``).
* word n-grams capture phrases ("viral video", "shared as").
* char n-grams survive spelling variation, Hinglish, and work for Hindi /
  Kannada without a language-specific tokenizer.
"""
from __future__ import annotations

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion

from ml.data_collection.verdict_normalizer import RULES
from ml.preprocessing.text_cleaning import WORD_TOKEN_PATTERN, model_text, normalize_whitespace


def build_vectorizer(max_word_features: int = 30000, max_char_features: int = 60000) -> FeatureUnion:
    return FeatureUnion([
        ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=2, max_df=0.9,
                                 sublinear_tf=True, max_features=max_word_features,
                                 token_pattern=WORD_TOKEN_PATTERN)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=3, sublinear_tf=True,
                                 max_features=max_char_features)),
    ])


def mask_verdict_cues(text: str) -> str:
    """Remove the exact words our verdict rules key on (anti-leakage for headline text)."""
    for rule in RULES:
        text = rule.pattern.sub(" ", text)
    return normalize_whitespace(text)


def prepare_training_frame(df: pd.DataFrame, min_class_size: int = 30, include_titles: bool = True) -> pd.DataFrame:
    """Select labelled rows and build the model input column ``text``.

    * claim_field rows: the circulating claim as written before the verdict.
    * title rows (Alt News): the headline WITH verdict cue words masked.
    Classes with fewer than ``min_class_size`` rows are dropped (too few to learn
    or evaluate); which classes survived is written into the model metadata.
    """
    d = df[df["verdict"].notna()].copy()
    if not include_titles:
        d = d[d["claim_source"] == "claim_field"]
    d["text"] = [model_text(t) if src == "claim_field" else model_text(mask_verdict_cues(t))
                 for t, src in zip(d["claim_text"], d["claim_source"])]
    d = d[d["text"].str.len() >= 10]
    counts = d["verdict"].value_counts()
    keep = counts[counts >= min_class_size].index
    d = d[d["verdict"].isin(keep)].rename(columns={"verdict": "label"})
    return d.reset_index(drop=True)


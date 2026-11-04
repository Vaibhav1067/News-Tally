"""Evaluation metrics, including calibration.

Why macro-F1? Our classes are imbalanced (fact-checkers publish far more
FALSE verdicts than OUTDATED ones). Accuracy and weighted-F1 reward a model
that ignores small classes; macro-F1 averages per-class F1 equally, so every
class counts.

Why ECE? A model saying "80% confident" should be right ~80% of the time.
Expected Calibration Error measures the gap. We show confidence to users,
so it must be checked, not assumed.
"""
from __future__ import annotations

import numpy as np
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support,
                             precision_score, recall_score)


def expected_calibration_error(y_true: np.ndarray, proba: np.ndarray, classes: list[str], n_bins: int = 10) -> dict:
    conf = proba.max(axis=1)
    pred = np.array(classes)[proba.argmax(axis=1)]
    correct = (pred == np.asarray(y_true)).astype(float)
    bins = np.linspace(0, 1, n_bins + 1)
    ece, table = 0.0, []
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (conf > lo) & (conf <= hi)
        if not m.any():
            continue
        acc, avg_conf = correct[m].mean(), conf[m].mean()
        ece += m.mean() * abs(acc - avg_conf)
        table.append({"bin": f"{lo:.1f}-{hi:.1f}", "count": int(m.sum()),
                      "accuracy": round(float(acc), 4), "avg_confidence": round(float(avg_conf), 4)})
    return {"ece": round(float(ece), 4), "bins": table}


def classification_metrics(y_true, y_pred, classes: list[str], proba: np.ndarray | None = None) -> dict:
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=classes, zero_division=0)
    out = {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision_macro": round(float(precision_score(y_true, y_pred, average="macro", labels=classes, zero_division=0)), 4),
        "recall_macro": round(float(recall_score(y_true, y_pred, average="macro", labels=classes, zero_division=0)), 4),
        "f1_macro": round(float(f1_score(y_true, y_pred, average="macro", labels=classes, zero_division=0)), 4),
        "f1_weighted": round(float(f1_score(y_true, y_pred, average="weighted", labels=classes, zero_division=0)), 4),
        "per_class": {c: {"precision": round(float(p[i]), 4), "recall": round(float(r[i]), 4),
                          "f1": round(float(f[i]), 4), "support": int(s[i])} for i, c in enumerate(classes)},
        "confusion_matrix": {"labels": classes,
                             "matrix": confusion_matrix(y_true, y_pred, labels=classes).tolist()},
        "n": int(len(y_true)),
    }
    if proba is not None:
        out["calibration"] = expected_calibration_error(np.asarray(y_true), proba, classes)
    return out

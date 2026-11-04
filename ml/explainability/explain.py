"""Explanations for the deployed classical classifier.

For a *linear* model on features x, the logit for class c is
    f_c(x) = b_c + sum_i w_ci * x_i
and SHAP values (interventional, independent features — exactly what
``shap.LinearExplainer`` computes) are
    phi_ci = w_ci * (x_i - E[x_i])
where E[x_i] is the mean feature value over the training data. The phi's sum
to f_c(x) - E[f_c(X)], i.e. they fully account for how this input moved the
class score away from the average input.

We compute this directly with sparse algebra (milliseconds per request) and
verify it against the ``shap`` library in notebooks/07_model_explainability.ipynb.

Caveat shown to users: a high SHAP value means "this n-gram pushed the MODEL
towards the label", not "this word is misinformation".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import scipy.sparse as sp


@dataclass
class FeatureContribution:
    feature: str
    kind: str  # "word" | "char"
    contribution: float


def _linear_weights(clf) -> tuple[Optional[np.ndarray], Optional[np.ndarray], str]:
    """Return (W [n_classes, n_features], b, method) or (None, None, reason)."""
    if hasattr(clf, "coef_"):
        W, b = np.asarray(clf.coef_), np.asarray(clf.intercept_)
        if W.shape[0] == 1:  # binary: sklearn stores one row for the positive class
            W, b = np.vstack([-W, W]), np.hstack([-b, b])
        return W, b, "exact_linear_shap"
    # CalibratedClassifierCV(LinearSVC): average the fold models' margins (approximation)
    if hasattr(clf, "calibrated_classifiers_"):
        Ws, bs = [], []
        for cc in clf.calibrated_classifiers_:
            est = getattr(cc, "estimator", None) or getattr(cc, "base_estimator", None)
            if est is None or not hasattr(est, "coef_"):
                return None, None, "unsupported"
            Ws.append(est.coef_), bs.append(est.intercept_)
        return np.mean(Ws, axis=0), np.mean(bs, axis=0), "approx_linear_shap_svm_margin"
    return None, None, "unsupported"


class LinearExplainer:
    def __init__(self, pipeline, background_mean: Optional[np.ndarray] = None):
        self.features = pipeline.named_steps["features"]
        self.clf = pipeline.named_steps["clf"]
        self.classes = list(pipeline.classes_)
        self.W, self.b, self.method = _linear_weights(self.clf)
        self.names, self.kinds = [], []
        for name, vec in self.features.transformer_list:
            fn = vec.get_feature_names_out()
            self.names.extend(fn.tolist())
            self.kinds.extend([name] * len(fn))
        self.names, self.kinds = np.array(self.names, dtype=object), np.array(self.kinds, dtype=object)
        self.mean = background_mean

    @property
    def available(self) -> bool:
        return self.W is not None

    def fit_background(self, texts: list[str]) -> "LinearExplainer":
        X = self.features.transform(texts)
        self.mean = np.asarray(X.mean(axis=0)).ravel()
        return self

    def explain(self, text: str, target_class: Optional[str] = None, top_k: int = 12) -> dict:
        if not self.available:
            return {"available": False, "method": self.method,
                    "reason": "The deployed model is not linear; no faithful explanation method is wired in."}
        x = self.features.transform([text])
        x = sp.csr_matrix(x)
        c = self.classes.index(target_class) if target_class else int(np.argmax(x @ self.W.T + self.b))
        w = self.W[c]
        mean = self.mean if self.mean is not None else np.zeros_like(w)
        # Only features present in the text get a "this word" explanation; the
        # absent-feature term (-w*mean summed over all others) is reported as one number.
        idx = x.indices
        present = w[idx] * (x.data - mean[idx])
        absent_total = float(-(w * mean).sum() + (w[idx] * mean[idx]).sum())
        order = np.argsort(-np.abs(present))[:top_k]
        contribs = [FeatureContribution(str(self.names[idx[i]]), str(self.kinds[idx[i]]),
                                        round(float(present[i]), 5)) for i in order]
        base = float(self.b[c] + w @ mean)
        return {
            "available": True,
            "method": self.method,
            "target_class": self.classes[c],
            "base_value": round(base, 5),
            "output_value": round(float((x @ w)[0] + self.b[c]), 5),
            "absent_features_contribution": round(absent_total, 5),
            "top_features": [c_.__dict__ for c_ in contribs],
            "token_highlights": token_highlights(text, contribs),
            "note": ("Contributions are SHAP values for the model's class score (log-odds scale). "
                     "They describe model behaviour, not proof that a word indicates misinformation."),
        }


def token_highlights(text: str, contribs: list[FeatureContribution]) -> list[dict]:
    """Project word-level and char-level contributions back onto whitespace tokens."""
    tokens = text.split()
    scores = np.zeros(len(tokens))
    low = [t.casefold() for t in tokens]
    for fc in contribs:
        f = fc.feature.casefold().strip()
        if not f:
            continue
        if fc.kind == "word":
            parts = f.split()
            for i in range(len(low) - len(parts) + 1):
                if all(parts[j] in low[i + j] for j in range(len(parts))):
                    for j in range(len(parts)):
                        scores[i + j] += fc.contribution / len(parts)
        else:
            hits = [i for i, t in enumerate(low) if f in f" {t} "]
            for i in hits:
                scores[i] += fc.contribution / max(len(hits), 1)
    return [{"token": t, "score": round(float(s), 5)} for t, s in zip(tokens, scores)]

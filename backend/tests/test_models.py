"""Model artifact tests: predictions, explanation faithfulness, retrieval, split leakage."""
from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
import pytest

from conftest import ARTIFACTS, ROOT, requires_models

pytestmark = requires_models


@pytest.fixture(scope="module")
def clf():
    return joblib.load(ARTIFACTS / "classifier.joblib")


def test_predict_proba_valid(clf):
    p = clf.predict_proba(["viral video shows army firing at protesters in delhi", "पुराना वीडियो वायरल"])
    assert p.shape[0] == 2 and np.allclose(p.sum(axis=1), 1)


def test_explanation_is_additive(clf):
    """SHAP efficiency: base + present contributions + absent term == model output (log-odds)."""
    from ml.explainability.explain import LinearExplainer

    mean = np.load(ARTIFACTS / "explainer_background_mean.npy")
    ex = LinearExplainer(clf, background_mean=mean)
    out = ex.explain("viral video claims the rbi has banned ₹500 notes", top_k=100000)
    total = out["base_value"] + sum(f["contribution"] for f in out["top_features"]) + out["absent_features_contribution"]
    assert abs(total - out["output_value"]) < 1e-3
    assert out["method"] == "exact_linear_shap"


def test_explanation_matches_shap_library(clf):
    shap = pytest.importorskip("shap")
    from ml.explainability.explain import LinearExplainer

    feats = clf.named_steps["features"]
    df = pd.read_csv(ROOT / "data" / "processed" / "factchecks.csv").dropna(subset=["verdict"]).head(100)  # shap subsamples >100
    bg = feats.transform(df["claim_text"].str.lower())
    ex = LinearExplainer(clf).fit_background(df["claim_text"].str.lower().tolist())
    text = "old video of flood shared as recent"
    x = feats.transform([text])
    c = list(clf.classes_).index("OUTDATED")
    lib = shap.LinearExplainer((clf.named_steps["clf"].coef_[c], clf.named_steps["clf"].intercept_[c]), bg)
    lib_vals = np.asarray(lib.shap_values(x)).ravel()
    ours = ex.explain(text, target_class="OUTDATED", top_k=5)["top_features"]
    names = list(ex.names)
    for f in ours:
        i = names.index(f["feature"]) if names.count(f["feature"]) == 1 else None
        if i is not None:
            assert abs(lib_vals[i] - f["contribution"]) < 1e-4


def test_retrieval_finds_known_claim():
    from ml.retrieval.index import FactCheckIndex

    idx = FactCheckIndex.load()
    df = pd.read_csv(ROOT / "data" / "processed" / "factchecks.csv")
    row = df[df["claim_source"] == "claim_field"].iloc[0]
    hits = idx.search(row["claim_text"], k=5)
    assert row["claim_id"] in [h.claim_id for h in hits]


def test_no_group_leakage_in_split():
    from ml.training.features import prepare_training_frame
    from ml.training.splits import group_split

    df = pd.read_csv(ROOT / "data" / "processed" / "factchecks.csv")
    tr, va, te = group_split(prepare_training_frame(df))
    assert not (set(tr.group_id) & set(te.group_id))
    assert not (set(tr.claim_id) & set(te.claim_id))

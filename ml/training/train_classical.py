"""Stage A — train and compare classical text classifiers.

    python -m ml.training.train_classical

What the model predicts (read this before trusting any number below):
    Given the text of a claim that a fact-checker chose to investigate, which
    verdict category did the fact-checker assign (FALSE / MISLEADING / OUTDATED ...)?

It does NOT predict whether an arbitrary sentence is true. Almost every
training example is a claim that was suspicious enough to be fact-checked,
so the model has seen very few true claims (selection bias). The risk
engine therefore never treats this classifier alone as evidence of falsity.

Models: Dummy baselines, Multinomial Naive Bayes, Logistic Regression, Linear SVM.
Selection is on VALIDATION macro-F1; the test set is touched once at the end.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import ComplementNB, MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from ml.config import ARTIFACTS_DIR, PROCESSED_DATASET, RANDOM_SEED
from ml.evaluation.metrics import classification_metrics
from ml.training.features import build_vectorizer, prepare_training_frame
from ml.training.splits import group_split

log = logging.getLogger("train_classical")


def candidate_models() -> dict:
    return {
        "dummy_most_frequent": DummyClassifier(strategy="most_frequent"),
        "dummy_stratified": DummyClassifier(strategy="stratified", random_state=RANDOM_SEED),
        "multinomial_nb": MultinomialNB(alpha=0.1),
        "complement_nb": ComplementNB(alpha=0.3),
        "logistic_regression": LogisticRegression(C=4.0, max_iter=3000, class_weight="balanced",
                                                  random_state=RANDOM_SEED),
        # LinearSVC has no predict_proba; wrap it in Platt/sigmoid calibration (cv on train folds)
        "linear_svm": CalibratedClassifierCV(LinearSVC(C=0.5, class_weight="balanced", random_state=RANDOM_SEED),
                                             method="sigmoid", cv=3),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    np.random.seed(RANDOM_SEED)
    df = pd.read_csv(PROCESSED_DATASET)
    data = prepare_training_frame(df, min_class_size=30, include_titles=True)
    classes = sorted(data["label"].unique().tolist())
    train, val, test = group_split(data)
    log.info("rows: train=%d val=%d test=%d classes=%s", len(train), len(val), len(test), classes)

    results = {}
    fitted = {}
    for name, clf in candidate_models().items():
        t0 = time.time()
        pipe = Pipeline([("features", build_vectorizer()), ("clf", clf)])
        pipe.fit(train["text"], train["label"])
        proba = pipe.predict_proba(val["text"])
        pred = pipe.classes_[proba.argmax(axis=1)]
        m = classification_metrics(val["label"], pred, classes, proba)
        m["train_seconds"] = round(time.time() - t0, 2)
        results[name] = {"validation": m}
        fitted[name] = pipe
        log.info("%-22s val macro-F1=%.3f acc=%.3f ECE=%.3f", name, m["f1_macro"], m["accuracy"],
                 m["calibration"]["ece"])

    real = {k: v for k, v in results.items() if not k.startswith("dummy")}
    best_name = max(real, key=lambda k: real[k]["validation"]["f1_macro"])
    # Prefer logistic regression when it is within 0.02 macro-F1 of the best:
    # its coefficients give exact, cheap per-feature explanations (see explainability/).
    lr_f1 = real["logistic_regression"]["validation"]["f1_macro"]
    deployed = "logistic_regression" if real[best_name]["validation"]["f1_macro"] - lr_f1 <= 0.02 else best_name
    log.info("best on validation: %s ; deployed: %s", best_name, deployed)

    # Test ONCE: every model is reported on test for the comparison table,
    # but only the validation scores were used to choose.
    for name, pipe in fitted.items():
        proba = pipe.predict_proba(test["text"])
        pred = pipe.classes_[proba.argmax(axis=1)]
        results[name]["test"] = classification_metrics(test["label"], pred, classes, proba)

    # Per-language / per-input-type breakdown for the deployed model (fairness check)
    dep = fitted[deployed]
    breakdown = {}
    for col in ("language", "claim_source"):
        breakdown[col] = {}
        for value, part in test.groupby(col):
            if len(part) < 10:
                continue
            p = dep.predict(part["text"])
            breakdown[col][str(value)] = classification_metrics(part["label"], p, classes)
    # Save test predictions for error analysis (notebook 08)
    test_out = test[["claim_id", "claim_text", "text", "label", "language", "claim_source", "publisher",
                     "fact_check_url"]].copy()
    proba = dep.predict_proba(test["text"])
    test_out["predicted"] = dep.classes_[proba.argmax(axis=1)]
    test_out["confidence"] = proba.max(axis=1).round(4)
    test_out.to_csv(ARTIFACTS_DIR / "test_predictions.csv", index=False, encoding="utf-8")

    joblib.dump(dep, ARTIFACTS_DIR / "classifier.joblib")
    # Background distribution for SHAP: mean TF-IDF vector over the TRAINING set only.
    background = np.asarray(dep.named_steps["features"].transform(train["text"]).mean(axis=0)).ravel()
    np.save(ARTIFACTS_DIR / "explainer_background_mean.npy", background.astype(np.float32))
    meta = {
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "deployed_model": deployed,
        "best_validation_model": best_name,
        "classes": classes,
        "task": "Predict the verdict category a fact-checker assigned to a claim that was fact-checked.",
        "n_train": len(train), "n_val": len(val), "n_test": len(test),
        "label_distribution_train": train["label"].value_counts().to_dict(),
        "language_distribution_train": train["language"].value_counts().to_dict(),
        "split": "StratifiedGroupKFold on near-duplicate groups (70/15/15)",
        "features": "TF-IDF word 1-2grams (30k) + char_wb 2-5grams (60k)",
        "seed": RANDOM_SEED,
        "results": results,
        "deployed_breakdown_test": breakdown,
        "dataset_file": str(PROCESSED_DATASET.name),
    }
    (ARTIFACTS_DIR / "classifier_metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False),
                                                           encoding="utf-8")
    write_comparison_report(meta)
    log.info("Saved classifier.joblib + classifier_metadata.json + model_comparison.md")


def write_comparison_report(meta: dict) -> None:
    lines = ["# Classical model comparison", "",
             f"Generated {meta['trained_at']} by `ml/training/train_classical.py`. Numbers are computed, not edited.", "",
             f"Task: {meta['task']}", f"Classes: {', '.join(meta['classes'])}",
             f"Rows: train {meta['n_train']} / val {meta['n_val']} / test {meta['n_test']} — split: {meta['split']}", "",
             "| Model | Val macro-F1 | Test macro-F1 | Test accuracy | Test weighted-F1 | Test ECE |",
             "|---|---|---|---|---|---|"]
    for name, r in meta["results"].items():
        v, t = r["validation"], r["test"]
        lines.append(f"| {name} | {v['f1_macro']:.3f} | {t['f1_macro']:.3f} | {t['accuracy']:.3f} | "
                     f"{t['f1_weighted']:.3f} | {t['calibration']['ece']:.3f} |")
    lines += ["", f"Deployed: **{meta['deployed_model']}** (best on validation: {meta['best_validation_model']}).", "",
              "## Per-class test results (deployed model)", "", "| Class | Precision | Recall | F1 | Support |",
              "|---|---|---|---|---|"]
    for c, s in meta["results"][meta["deployed_model"]]["test"]["per_class"].items():
        lines.append(f"| {c} | {s['precision']:.3f} | {s['recall']:.3f} | {s['f1']:.3f} | {s['support']} |")
    lines += ["", "## Deployed model by language / input type (test)", "", "| Slice | n | Macro-F1 | Accuracy |",
              "|---|---|---|---|"]
    for col, parts in meta["deployed_breakdown_test"].items():
        for val, m in parts.items():
            lines.append(f"| {col}={val} | {m['n']} | {m['f1_macro']:.3f} | {m['accuracy']:.3f} |")
    (ARTIFACTS_DIR / "model_comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

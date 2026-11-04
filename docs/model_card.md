# Model card — NEWS TALLY verdict-type classifier and retrieval index

## Model details

| | |
|---|---|
| Classifier | scikit-learn `LogisticRegression(C=4, class_weight="balanced")` on TF-IDF word 1–2-grams (30k) + char_wb 2–5-grams (60k) |
| Artifact | `ml/artifacts/classifier.joblib` (+ `classifier_metadata.json`, `explainer_background_mean.npy`) |
| Retrieval | hybrid: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (Apache-2.0) + char TF-IDF; `ml/artifacts/retrieval/` |
| Trained | 2026-11-04, seed 42, CPU, < 1 minute |
| Code | `ml/training/train_classical.py`, `ml/retrieval/index.py` |

## Intended use

* Give a reader a **signal** about which kind of debunk (FALSE / MISLEADING / OUTDATED) previously
  fact-checked claims resembling their text received, as one input to a rule-gated assessment.
* Retrieve published fact-checks that may concern the same claim.

**Out of scope:** deciding whether a claim is true; moderating or removing content; judging people,
parties, communities or outlets; any language other than English, Hindi and Kannada; images and
videos themselves.

## Training data

4,137 fact-checks from Factly (English, Kannada) and Alt News (English, Hindi), 2019–2026, labels
derived from publishers' wording by rules (`docs/data_sources.md`). Training uses 3,629 labelled rows
in the three classes with ≥ 30 examples, split 2,591 / 519 / 519 by near-duplicate group.

| Class | Train share |
|---|---|
| FALSE | ~42% |
| MISLEADING | ~37% |
| OUTDATED | ~21% |

## Metrics (held-out test set, n = 519)

| Metric | Value |
|---|---|
| Macro-F1 | 0.527 (stratified random baseline 0.305; majority baseline 0.198) |
| Accuracy | 0.555 |
| Weighted-F1 | 0.551 |
| ECE (10 bins) | 0.125 |
| F1 by class | FALSE 0.603 · MISLEADING 0.574 · OUTDATED 0.404 |
| Macro-F1 by language | English 0.491 · Hindi 0.500 · Kannada 0.458 |

### Transformer comparison (same splits)

| Model | Val macro-F1 | Test macro-F1 | Test acc. | ECE | Train time (CPU) |
|---|---|---|---|---|---|
| **TF-IDF + Logistic Regression (deployed)** | 0.584 | 0.527 | 0.555 | 0.125 | < 1 min |
| MiniLM-multilingual, frozen embeddings + LR | 0.514 | 0.509 | 0.528 | 0.066 | 25 s |
| MiniLM-multilingual, fine-tuned (best of 3 epochs: 2) | 0.590 | **0.560** | 0.576 | **0.028** | 9 min |

Fine-tuned per-class test F1: FALSE 0.625 · MISLEADING 0.576 · OUTDATED 0.479.

**Why LR is still deployed.** Selection was made on validation, where the two are effectively tied
(0.590 vs 0.584). The fine-tuned model is better on test (+0.033 macro-F1, much better calibrated),
but with n = 519 that gap is within roughly one standard error, and it costs ~500 MB extra RAM and
has no exact explanation method. Deploying it (with a gradient-based or perturbation explainer)
is the first item on the roadmap. Frozen paraphrase embeddings are *worse* than TF-IDF: they encode
topic, not the verdict type.

### Retrieval

Recall@1 0.845, recall@5 0.933, MRR 0.883 (1,500 claim queries, 4,137 headline documents). Top-1
precision 0.95 at the strong-match threshold 0.60.

## Limitations and risks

* **Selection bias**: almost no TRUE examples — the model cannot recognise a true claim and must
  not be used as a truth detector. The risk engine gives it 20% weight and no veto.
* **Label noise**: ~8% clear label errors and ~8% debatable boundaries (AI-performed audit, not
  independent annotators). Metrics are bounded by this noise.
* **Task difficulty**: whether a claim is OUTDATED often depends on facts outside the text.
* **Language and topic coverage**: three languages; political and communal claims dominate.
* **Temporal drift**: misinformation narratives change; retrain after re-collecting.
* **Retrieval false positives**: precision is measured for claims whose fact-check exists; for novel
  claims a high score may still be about a different event, so the UI asks users to verify.

## Explainability

Exact interventional SHAP values for the linear model (verified against `shap.LinearExplainer`).
They describe model behaviour, not evidence.

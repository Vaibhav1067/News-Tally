# Classical model comparison

Generated 2026-11-04T05:25:32+00:00 by `ml/training/train_classical.py`. Numbers are computed, not edited.

Task: Predict the verdict category a fact-checker assigned to a claim that was fact-checked.
Classes: FALSE, MISLEADING, OUTDATED
Rows: train 2591 / val 519 / test 519 — split: StratifiedGroupKFold on near-duplicate groups (70/15/15)

| Model | Val macro-F1 | Test macro-F1 | Test accuracy | Test weighted-F1 | Test ECE |
|---|---|---|---|---|---|
| dummy_most_frequent | 0.198 | 0.198 | 0.422 | 0.250 | 0.578 |
| dummy_stratified | 0.306 | 0.305 | 0.339 | 0.334 | 0.661 |
| multinomial_nb | 0.542 | 0.505 | 0.534 | 0.526 | 0.384 |
| complement_nb | 0.537 | 0.503 | 0.541 | 0.529 | 0.317 |
| logistic_regression | 0.584 | 0.527 | 0.555 | 0.551 | 0.125 |
| linear_svm | 0.545 | 0.506 | 0.574 | 0.549 | 0.062 |

Deployed: **logistic_regression** (best on validation: logistic_regression).

## Per-class test results (deployed model)

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| FALSE | 0.590 | 0.616 | 0.603 | 219 |
| MISLEADING | 0.559 | 0.591 | 0.574 | 193 |
| OUTDATED | 0.454 | 0.364 | 0.404 | 107 |

## Deployed model by language / input type (test)

| Slice | n | Macro-F1 | Accuracy |
|---|---|---|---|
| language=en | 299 | 0.491 | 0.562 |
| language=hi | 119 | 0.500 | 0.546 |
| language=kn | 101 | 0.458 | 0.545 |
| claim_source=claim_field | 247 | 0.525 | 0.575 |
| claim_source=title | 272 | 0.511 | 0.537 |

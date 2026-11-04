# Methodology

The website's Methodology page renders the same content with live numbers from the artifacts.
This file is the reference version for reviewers and interviews.

## 1. What the system claims, and what it does not

NEWS TALLY answers: *"Have professional fact-checkers published something about this claim, what
did they conclude, and how does a model trained on their work read this text?"*

It never answers "is this true?" on its own authority. The outcome is one of:

| Outcome | When |
|---|---|
| HIGH MISINFORMATION RISK | a **strong** match (score ≥ 0.60) to a fact-check rated FALSE |
| POTENTIALLY MISLEADING | strong match rated MISLEADING / OUTDATED, or related matches (≥ 0.40) whose weight is mostly risky verdicts |
| EVIDENCE SUPPORTS CLAIM | strong match rated TRUE |
| UNVERIFIED | no relevant fact-check; or related matches without a risky majority |
| INSUFFICIENT EVIDENCE | under 4 words, unsupported language, or a matched fact-check with an unparsed verdict |

**The classifier alone can never produce HIGH MISINFORMATION RISK** (enforced and unit-tested in
`backend/tests/test_risk_engine.py::test_classifier_alone_never_high_risk`).

## 2. NLP pipeline

1. HTML stripping (BeautifulSoup), Unicode NFC, zero-width removal, quote/dash normalisation.
2. Currency normalisation: `Rs 500`, `Rs.500`, `INR 500` → `₹500` (found via a failing smoke test).
3. URL extraction (kept as metadata; replaced by `URLTOKEN` for the model).
4. Language detection: Unicode script counts (deterministic for Indic scripts), `langdetect` for
   Latin script only, a Hinglish lexicon for romanised Hindi; ≥ 20% second-script share = mixed.
5. Tokenisation for word n-grams uses a custom pattern because Python's `\w` does not match Indic
   combining marks: `(?:[^\W_]|[ऀ-ൿ])(?:[^\W_]|[ऀ-ൿ])+`. Fixing this raised
   validation macro-F1 from 0.567 to 0.584.
6. No stop-word removal: TF-IDF's IDF already down-weights frequent words, and English stop-word
   lists would delete negations ("not", "no") that matter for claims.
7. No translation: the original text is analysed and preserved.

## 3. Classification

**Task.** Predict the verdict category that a fact-checker assigned to a claim that was
fact-checked. Classes with ≥ 30 examples: FALSE, MISLEADING, OUTDATED.

**Input text.** Factly `Claim:` text where available (written before the verdict); otherwise the
headline **with verdict cue words masked** (`mask_verdict_cues`) to prevent label leakage.

**Splits.** 70/15/15 with `StratifiedGroupKFold`, groups = near-duplicate clusters (char 3–5-gram
TF-IDF cosine ≥ 0.8, union-find). An assertion fails training if any group crosses a split.

**Features.** `FeatureUnion` of word 1–2-grams (30k, min_df 2) and char_wb 2–5-grams (60k, min_df 3),
sublinear TF.

**Results (test set, n = 519; see `ml/artifacts/model_comparison.md`).**

| Model | Val macro-F1 | Test macro-F1 | Test acc. | ECE |
|---|---|---|---|---|
| Dummy (stratified) | 0.306 | 0.305 | 0.339 | 0.661 |
| Multinomial NB | 0.542 | 0.505 | 0.534 | 0.384 |
| Complement NB | 0.537 | 0.503 | 0.541 | 0.317 |
| **Logistic Regression (deployed)** | **0.584** | **0.527** | 0.555 | 0.125 |
| Linear SVM (sigmoid-calibrated) | 0.545 | 0.506 | 0.574 | 0.062 |

Per class (LR): FALSE F1 0.603, MISLEADING 0.574, OUTDATED 0.404. By language: en 0.491, hi 0.500,
kn 0.458 macro-F1.

Transformer (same splits): frozen MiniLM embeddings + LR 0.509 test macro-F1; fine-tuned MiniLM 0.560 test
macro-F1 (val 0.590, ECE 0.028). LR stays deployed (validation tie, explainability, RAM); details and
reasoning in `docs/model_card.md`.

## 4. Retrieval

Documents = fact-check headlines. Score = 0.5·cos(MiniLM-multilingual embeddings) +
0.5·cos(char 2–5-gram TF-IDF); lexical only when the query or document is Kannada (the dense model
was not trained on Kannada: recall@1 7.3% when used alone).

Evaluation (1,500 Factly claim texts as queries, 4,137 headlines as documents, correct = own article):

| Method | R@1 | R@5 | MRR |
|---|---|---|---|
| Dense only | 0.557 | 0.647 | — |
| TF-IDF only | 0.819 | 0.921 | 0.864 |
| multilingual-e5-small (tested, rejected) | 0.469 | 0.661 | — |
| **Hybrid, Kannada-aware (deployed)** | **0.845** | **0.933** | **0.883** |

Top-1 precision by threshold (hybrid): ≥ 0.40 → 0.87 (91% coverage); ≥ 0.50 → 0.90; ≥ 0.60 → 0.95
(55% coverage); ≥ 0.70 → 0.99. Thresholds: strong 0.60, related 0.40.

Limitations: precision is measured on queries whose answer **is** in the index; for out-of-dataset
claims, a high score can still be a different event. Hindi and cross-lingual retrieval are not
quantitatively evaluated (no Hindi claim texts exist to use as queries).

## 5. Risk index

```
R  = 100 × (0.65·E + 0.20·C + 0.15·S)
w_m = clip((sim_m − 0.40) / 0.60, 0, 1) × max(0.7, 1 − 0.1·age_years)
E  = max(w)·Σ w_m·risk(v_m)/Σ w_m + (1 − max(w))·0.5          (0.5 when no relevant match)
C  = Σ_k p_k·risk(k)  if language supported and ≥ 4 words, else 0.5
S  = 0 if the submitted URL is itself a fact-check, else 0.5
risk: FALSE 1.0 · MISLEADING 0.75 · OUTDATED 0.65 · UNVERIFIED 0.5 · INSUFFICIENT 0.5 · TRUE 0
Evidence strength = 0.70·max(w) + 0.20·p_max·[in domain] + 0.10·[source known]
```

Design reasons: missing evidence is neutral (0.5), never "safe"; weak matches move E only a
little; the classifier's 0.20 weight reflects its measured weakness (macro-F1 0.53); outlet
reputation is not used to judge claims. **The weights are design choices, not fitted, and R is not a
calibrated probability** — the UI says so next to the number.

## 6. Explainability

For the linear model, SHAP values are computed exactly as φ_i = w_ci·(x_i − E[x_i]) with E[x] the
training-set mean feature vector. Tests verify additivity (base + Σφ = logit) and agreement with
`shap.LinearExplainer` to < 1e-4. Word- and char-n-gram contributions are projected back onto input
tokens for highlighting. If a non-linear model is deployed, explanations are reported as unavailable.

## 7. Bias, fairness and safeguards

* Selection bias: 99.7% of parsed verdicts are FALSE/MISLEADING/OUTDATED; the model has no notion of a true claim.
* Topic bias: politics and religion/communal claims dominate; the word "muslim" is among the top
  MISLEADING features of the classifier (notebook 07) — a dataset artifact the classifier's low weight and
  no-veto rule are designed to contain. Names of communities and parties in
  the data reflect what was debunked, not who spreads misinformation.
* Language gap: Kannada scores lowest; other Indian languages are detected and flagged as unsupported.
* Label noise: ~8% clear errors + ~8% debatable boundaries in rule-derived labels (AI-performed audit).
* Privacy: opt-in storage, 30-day purge, no request-body logging. Security: SSRF guard, size and rate limits.

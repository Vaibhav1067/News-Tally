# Roadmap and status

Status as of 2026-11-04. "Done" means implemented, run and checked; nothing here is a placeholder.

| Phase | Status | Notes |
|---|---|---|
| 1. Project setup and architecture | done | monorepo, venv, configs, docs |
| 2. Data collection and ingestion | done | Factly EN/KN + Alt News EN/HI via public WP APIs; BOOM/PIB refused access; manual importer for downloaded datasets |
| 3. Cleaning and EDA | done | validation, NFC, currency normalisation, exact + near-dup detection, report JSON, notebooks 02–03 |
| 4. Classical ML | done | NB ×2, LR, calibrated SVM, dummies; group-aware splits; macro-F1 + ECE |
| 5. Transformer experimentation | done (CPU, small model) | fine-tuned MiniLM: test macro-F1 0.560 vs LR 0.527; not yet deployed (see model card) |
| 6. Fact-check retrieval | done | hybrid dense + lexical, Kannada-aware, thresholds from evaluation |
| 7. Source evidence engine | done | mention-based coverage, no credibility scores |
| 8. Risk assessment | done | documented formula, rule-gated labels, unit-tested |
| 9. Explainable AI | done | exact linear SHAP, verified against `shap` |
| 10. Backend integration | done | 9 endpoints, validation, rate/size limits, SSRF guard, opt-in storage |
| 11. Frontend | done | landing, analysis, explorer, dataset dashboard, methodology |
| 12. Testing | done | 82 tests |
| 13. Deployment | **configured, not deployed** | Dockerfile, compose, `render.yaml`, `vercel.json`; needs your accounts |
| 14. Documentation | done | README, docs/, notebooks |

## Highest-value next steps

0. **Deploy the fine-tuned transformer** behind a flag, with an explainer (e.g. integrated gradients
   or occlusion) and repeated-seed evaluation to confirm the +0.033 test gain is not split noise.
1. **Human-verified labels.** Have two people label 300 records (κ agreement), measure the rule
   parser's precision properly, and train on corrected labels.
2. **Hindi claim texts.** Alt News Hindi has no "Claim:" block; extract the claim sentence from the
   article's first paragraph (or label 300 by hand) so Hindi stops relying on masked headlines.
3. **Indic encoders.** Evaluate IndicBERT v2 / MuRIL / LaBSE on a GPU (Colab) for both retrieval
   (especially Kannada) and classification.
4. **Non-debunked negatives.** Add verified-true claims (e.g. PIB press releases) so the model can
   learn what a true claim looks like; until then TRUE cannot be predicted.
5. **More sources.** Ask BOOM Live and PIB for permission or a dataset; add Vishvas News, Newschecker
   if their terms allow.
6. **Image/video claims.** Most debunks concern media; reverse-image search is out of scope today.

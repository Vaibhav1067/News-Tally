# Verdict-parser audit log

The verdict labels in this dataset come from transparent regex rules
(`ml/data_collection/verdict_normalizer.py`), not from human annotation.
To estimate their quality, random samples of English + Hindi records were read
and judged against the headline. **The reviewer was the AI coding assistant
that wrote the rules, not an independent annotator**: treat these figures as
rough estimates and re-audit them yourself (see "How to audit" below).

## Audit 1 — 2026-11-04, sample seed 7, n = 45 (41 parsed)
Systematic errors found:
* "The video is NOT a deepfake" was labelled FALSE (the negation was ignored).
* "falsely shared as" with real footage was labelled FALSE in some rows and MISLEADING in others.
* Missed: "did not make the statement", "... is edited", "predates", "is shared as showing".

Fixed via new rules (`en_not_manipulated`, extended `en_misleading`, `en_false`, `en_outdated`).
Re-normalising the existing raw data with the new rules changed 494 labels.

## Audit 2 — 2026-11-04 (after fixes), sample seed 123, n = 40 (39 parsed)
* Clear errors: 3/39 (~8%)
  * a news report (not a fact-check) mentioning "fake drug cases" was labelled FALSE;
  * "videos indeed from July 20 protests; PIB's 'fact check' incorrect" (the claim was actually TRUE) was labelled MISLEADING;
  * "police's claims that video is 'old and AI-generated' false" was labelled FALSE (the video was genuine).
* Debatable boundary calls: ~3/39 (FALSE vs MISLEADING vs OUTDATED).
* Unparsed: 1/40.

**Estimated label precision: about 85–92% on English/Hindi. Kannada was not audited by a fluent reader.**

## Consequences
* Model metrics are bounded by label noise. A macro-F1 near 0.9 would be suspicious.
* The MISLEADING / OUTDATED / FALSE boundaries are partly a matter of editorial convention.
* TRUE (6 rows), UNVERIFIED (1) and INSUFFICIENT_EVIDENCE (4) are too rare to train on.

## How to audit
```bash
python -c "import pandas as pd; d=pd.read_csv('data/processed/factchecks.csv'); print(d.sample(40, random_state=1)[['verdict','verdict_rule','fact_check_title']].to_string())"
```

"""Generate the research notebooks in notebooks/ (then execute them with nbconvert).

    python scripts/make_notebooks.py
    jupyter nbconvert --to notebook --execute --inplace notebooks/*.ipynb

Notebooks import the project's own modules instead of re-implementing them,
so what you read is exactly what the pipeline runs. Observations are written
against the measured results; re-check them if you re-collect data.
"""
from __future__ import annotations

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
NB_DIR = ROOT / "notebooks"
NB_DIR.mkdir(exist_ok=True)

SETUP = """import sys, json, warnings
from pathlib import Path
ROOT = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()
sys.path.insert(0, str(ROOT))
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import matplotlib.pyplot as plt, seaborn as sns
sns.set_theme(style='whitegrid', context='notebook')
plt.rcParams['figure.figsize'] = (9, 4)
from ml.config import PROCESSED_DATASET, ARTIFACTS_DIR, METADATA_DIR, RAW_DIR
df = pd.read_csv(PROCESSED_DATASET)
print(f'{len(df):,} processed fact-checks')"""


def nb(name: str, cells: list[tuple[str, str]]) -> None:
    book = nbf.v4.new_notebook()
    book.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    book.cells = [nbf.v4.new_markdown_cell(src) if kind == "md" else nbf.v4.new_code_cell(src) for kind, src in cells]
    nbf.write(book, NB_DIR / name)
    print("wrote", name)


nb("01_data_collection.ipynb", [
    ("md", "# 01 — Data collection\n\n**Objective.** Understand how fact-checks are collected legally and reproducibly, and inspect what one collection run produced.\n\n"
           "Sources are read through their public WordPress REST APIs after checking `robots.txt`. BOOM Live (HTTP 403) and PIB Fact Check (HTTP 401) refused automated access and were **not** bypassed."),
    ("code", SETUP.replace("df = pd.read_csv(PROCESSED_DATASET)\nprint(f'{len(df):,} processed fact-checks')", "")),
    ("md", "## Source registry\nEach source declares its API root, language and whether posts must have a parseable verdict (Alt News mixes reporting with fact-checks)."),
    ("code", "from ml.data_collection.sources import SOURCES, UNAVAILABLE_SOURCES\npd.DataFrame([{**{k: getattr(s, k) for k in ('key','publisher','base_url','language','require_verdict')}} for s in SOURCES.values()])"),
    ("code", "pd.DataFrame([s.__dict__ for s in UNAVAILABLE_SOURCES])"),
    ("md", "## Parsing one post (offline example)\n`WordPressCollector.parse_post` turns an API post into a `FactCheckRecord`. We feed it a hand-written post so the notebook runs without network access."),
    ("code", "from ml.data_collection.wordpress_collector import WordPressCollector\nc = WordPressCollector(SOURCES['factly_en'])\nc._categories = {1: 'Politics'}\npost = {'title': {'rendered': 'Old video from Bangladesh falsely shared as police firing in Delhi'}, 'link': 'https://factly.in/example/',\n        'date': '2026-11-03T10:00:00', 'categories': [1], 'excerpt': {'rendered': '<p>A video is viral...</p>'},\n        'content': {'rendered': '<p>Claim: Video shows Delhi Police firing at protesters. Fact: The video is from Bangladesh (2024). To sum up, an old video from Bangladesh is being shared as Delhi.</p>'}}\nc.parse_post(post).to_dict()"),
    ("md", "## What the real collection run produced\nThe collection log records pages fetched, posts kept and dropped per source."),
    ("code", "runs = [json.loads(l) for l in (METADATA_DIR / 'collection_log.jsonl').read_text(encoding='utf-8').splitlines()]\npd.DataFrame([{**{'source': k}, **{x: v.get(x) for x in ('pages_fetched','posts_seen','kept','dropped_no_verdict','seconds')}} for r in runs for k, v in r['sources'].items()])"),
    ("code", "raw = pd.concat([pd.read_json(p, lines=True) for p in sorted(RAW_DIR.glob('*.jsonl'))])\nax = raw.groupby(['publisher','language']).size().plot.barh(color='#4a8ad6'); ax.set_xlabel('records'); ax.set_title('Raw records by publisher and language'); plt.show()"),
    ("md", "## Observations\n* Factly's fact-check categories give a clean stream; every Factly English article contains a `Claim:` block.\n* 34% (Hindi) to 41% (English) of Alt News posts were dropped because no verdict rule matched; most are reporting rather than fact-checks.\n* Only headlines, the circulating claim and a one-sentence conclusion are stored — never full articles.\n\n**Conclusion.** The pipeline yields ~4.1k attributable Indian fact-checks in three languages without bypassing any access control."),
])

nb("02_data_cleaning.ipynb", [
    ("md", "# 02 — Data cleaning\n\n**Objective.** Apply and inspect cleaning, validation, verdict normalisation and de-duplication."),
    ("code", SETUP),
    ("md", "## Text normalisation\nThe same `clean_text` runs at training and inference time (no training/serving skew)."),
    ("code", "from ml.preprocessing.text_cleaning import clean_text, model_text, WORD_TOKEN_PATTERN\nimport re\nfor s in ['<p>Rs 500 notes&nbsp;banned!!</p>', 'यह\\u200b वीडियो पुराना है', 'Check https://x.com/abc NOW']:\n    print(repr(s), '->', repr(clean_text(s)), '| model:', repr(model_text(s)))\nprint(re.findall(r'(?u)\\b\\w\\w+\\b', 'प्रदर्शनकारियों पर'), 'vs', re.findall(WORD_TOKEN_PATTERN, 'प्रदर्शनकारियों पर'))"),
    ("md", "The last line shows a real bug we fixed: Python's `\\w` does not match Indic vowel signs, so the default scikit-learn token pattern splits Hindi words into fragments."),
    ("md", "## Verdict normalisation\nOrdered regex rules; unmatched records stay unlabelled."),
    ("code", "ax = df['verdict_rule'].fillna('— no rule —').value_counts().head(15).plot.barh(color='#4a8ad6'); ax.invert_yaxis(); ax.set_title('Which rule labelled each record'); plt.show()"),
    ("code", "df.sample(12, random_state=3)[['verdict','verdict_rule','fact_check_title']]"),
    ("md", "## De-duplication and near-duplicate groups"),
    ("code", "rep = json.loads((METADATA_DIR / 'dataset_report.json').read_text(encoding='utf-8'))\n{k: rep[k] for k in ('raw_rows','invalid_rows','duplicate_urls','duplicate_claim_texts','near_duplicate_rows','near_duplicate_groups','verdicts_changed_by_renormalisation','final_rows')}"),
    ("code", "sizes = df.groupby('group_id').size(); g = sizes[sizes > 1].index[:3]\ndf[df.group_id.isin(g)].sort_values('group_id')[['group_id','publisher','language','claim_text']]"),
    ("md", "## Observations\n* Exact duplicates are rare (sources rarely re-publish), but near-duplicate groups exist and are kept together during splitting.\n* Verdict labels have measurable noise (see `data/metadata/verdict_audit.md`: ~8% clear errors).\n\n**Conclusion.** The processed dataset is clean, attributable and honest about what it does not know."),
])

nb("03_exploratory_analysis.ipynb", [
    ("md", "# 03 — Exploratory data analysis\n\n**Objective.** Describe the dataset: verdicts, languages, categories, sources, time, text length, missing data. These statistics describe *what two newsrooms chose to fact-check*, not misinformation in India."),
    ("code", SETUP),
    ("code", "fig, axes = plt.subplots(1, 3, figsize=(15, 4))\ndf['verdict'].fillna('UNPARSED').value_counts().plot.bar(ax=axes[0], color='#4a8ad6', title='Verdicts')\ndf['language'].value_counts().plot.bar(ax=axes[1], color='#4a8ad6', title='Languages')\ndf['publisher'].value_counts().plot.bar(ax=axes[2], color='#4a8ad6', title='Publishers')\nplt.tight_layout(); plt.show()"),
    ("code", "pd.crosstab(df['language'], df['verdict'].fillna('UNPARSED'), margins=True)"),
    ("code", "ax = df['category'].fillna('Uncategorised').value_counts().head(12).plot.barh(color='#4a8ad6'); ax.invert_yaxis(); ax.set_title('Top categories (publisher tags + keyword inference)'); plt.show()\ndf['category_source'].fillna('none').value_counts()"),
    ("code", "ts = pd.to_datetime(df['publication_date']).dt.to_period('M').value_counts().sort_index()\nax = ts.plot(color='#4a8ad6'); ax.set_title('Fact-checks per month (reflects collection depth, not volume)'); plt.show()"),
    ("code", "ax = sns.histplot(data=df, x='claim_length_words', hue='language', bins=40, element='step'); ax.set_xlim(0, 80); ax.set_title('Claim length (words)'); plt.show()\ndf.groupby('language')['claim_length_words'].describe().round(1)"),
    ("code", "(df.isna().mean() * 100).round(1).sort_values(ascending=False).to_frame('missing %').head(10)"),
    ("md", "## Observations\n* FALSE, MISLEADING and OUTDATED make up ~99.7% of parsed verdicts — TRUE is nearly absent (selection bias).\n* Politics and religion/communal topics dominate, reflecting these publishers' priorities.\n* Claims are short (median ~20 words): TF-IDF features have little text to work with.\n\n**Conclusion.** A classifier trained here can only distinguish *types* of debunked claims; retrieval of matching fact-checks must carry the evidence."),
])

nb("04_baseline_models.ipynb", [
    ("md", "# 04 — Baseline models\n\n**Objective.** Train TF-IDF + Naive Bayes / Logistic Regression / Linear SVM with leakage-aware splits, and compare against dummy baselines."),
    ("code", SETUP),
    ("code", "from ml.training.features import prepare_training_frame, build_vectorizer, mask_verdict_cues\nfrom ml.training.splits import group_split\ndata = prepare_training_frame(df)\ntrain, val, test = group_split(data)\nprint(len(train), len(val), len(test)); train['label'].value_counts(normalize=True).round(3)"),
    ("md", "## Leakage check\nHeadlines contain the verdict (\"… is a deepfake\"). For title-only rows we mask the cue words before training:"),
    ("code", "for t in df[df.claim_source=='title'].fact_check_title.head(4): print(t, '\\n  ->', mask_verdict_cues(t))"),
    ("code", "from sklearn.pipeline import Pipeline\nfrom sklearn.linear_model import LogisticRegression\nfrom sklearn.naive_bayes import MultinomialNB\nfrom sklearn.dummy import DummyClassifier\nfrom sklearn.metrics import f1_score\nres = {}\nfor name, clf in {'dummy': DummyClassifier(strategy='stratified', random_state=42), 'nb': MultinomialNB(alpha=0.1),\n                  'logreg': LogisticRegression(C=4, max_iter=3000, class_weight='balanced')}.items():\n    p = Pipeline([('features', build_vectorizer()), ('clf', clf)]).fit(train.text, train.label)\n    res[name] = f1_score(val.label, p.predict(val.text), average='macro')\npd.Series(res).round(3).to_frame('validation macro-F1')"),
    ("md", "## The full, saved comparison (from `ml/training/train_classical.py`)"),
    ("code", "meta = json.loads((ARTIFACTS_DIR / 'classifier_metadata.json').read_text())\npd.DataFrame({k: {'val_macro_f1': v['validation']['f1_macro'], 'test_macro_f1': v['test']['f1_macro'], 'test_acc': v['test']['accuracy'], 'test_ece': v['test']['calibration']['ece']} for k, v in meta['results'].items()}).T"),
    ("md", "## Observations\n* All real models beat the stratified baseline (~0.31 macro-F1) by a wide margin, but none exceeds ~0.6.\n* Logistic Regression is best on validation and best calibrated after the SVM.\n\n**Conclusion.** Deploy Logistic Regression: competitive and exactly explainable."),
])

nb("05_model_comparison.ipynb", [
    ("md", "# 05 — Model comparison\n\n**Objective.** Compare all models on the held-out test set: macro-F1, per-class results, confusion matrix, calibration and per-language fairness."),
    ("code", SETUP),
    ("code", "meta = json.loads((ARTIFACTS_DIR / 'classifier_metadata.json').read_text())\ncomp = pd.DataFrame({k: {m: v['test'][m] for m in ('accuracy','f1_macro','f1_weighted','precision_macro','recall_macro')} for k, v in meta['results'].items()}).T\nax = comp['f1_macro'].sort_values().plot.barh(color='#4a8ad6'); ax.set_title('Test macro-F1'); plt.show(); comp.round(3)"),
    ("code", "dep = meta['results'][meta['deployed_model']]['test']\ncm = pd.DataFrame(dep['confusion_matrix']['matrix'], index=dep['confusion_matrix']['labels'], columns=dep['confusion_matrix']['labels'])\nsns.heatmap(cm, annot=True, fmt='d', cmap='Blues'); plt.ylabel('fact-checker verdict'); plt.xlabel('predicted'); plt.show()\npd.DataFrame(dep['per_class']).T"),
    ("code", "cal = pd.DataFrame(dep['calibration']['bins'])\nplt.plot([0,1],[0,1],'--',color='grey'); plt.plot(cal.avg_confidence, cal.accuracy, 'o-', color='#4a8ad6'); plt.xlabel('confidence'); plt.ylabel('accuracy'); plt.title(f\"Reliability diagram, ECE={dep['calibration']['ece']}\"); plt.show()"),
    ("code", "pd.DataFrame({f'{c}={k}': v for c, parts in meta['deployed_breakdown_test'].items() for k, v in parts.items()}).T[['n','f1_macro','accuracy']]"),
    ("md", "## Observations\n* OUTDATED has the lowest recall: whether a video is old is rarely visible in the claim's wording.\n* Kannada scores lowest of the three languages.\n* Confidence is moderately calibrated; the UI therefore shows probabilities but never treats them as truth.\n\n**Conclusion.** The classifier is a weak signal (20% weight in the risk index); evidence retrieval must dominate."),
])

nb("06_transformer_experiments.ipynb", [
    ("md", "# 06 — Transformer experiments\n\n**Objective.** Test whether a multilingual transformer beats TF-IDF on the same splits. Training is run by `python -m ml.training.train_transformer` (CPU, ~10 minutes); this notebook reads its saved metrics instead of retraining."),
    ("code", SETUP),
    ("code", "p = ARTIFACTS_DIR / 'transformer' / 'transformer_metrics.json'\ntm = json.loads(p.read_text()) if p.exists() else None\nprint('metrics found' if tm else 'run python -m ml.training.train_transformer first')"),
    ("code", "if tm:\n    rows = {'classical LR (deployed)': tm.get('classical_reference', {})}\n    if 'frozen_embeddings_lr' in tm: rows['MiniLM frozen + LR'] = {'validation_macro_f1': tm['frozen_embeddings_lr']['validation']['f1_macro'], 'test_macro_f1': tm['frozen_embeddings_lr']['test']['f1_macro']}\n    if 'finetune' in tm: rows['MiniLM fine-tuned'] = {'validation_macro_f1': tm['finetune']['validation']['f1_macro'], 'test_macro_f1': tm['finetune']['test']['f1_macro']}\n    display(pd.DataFrame(rows).T)"),
    ("code", "if tm and 'finetune' in tm:\n    h = pd.DataFrame(tm['finetune']['history']).set_index('epoch')\n    h[['train_loss','val_f1_macro']].plot(marker='o', subplots=True, layout=(1,2), figsize=(10,3)); plt.show(); display(h)"),
    ("md", "## Observations\n* Frozen sentence embeddings + LR are *worse* than TF-IDF: the paraphrase model encodes topic, not verdict type.\n* Full fine-tuning ties LR on validation (0.590 vs 0.584) and beats it on test (0.560 vs 0.527) with far better calibration, at ~3 minutes of CPU per epoch.\n* LR stays deployed for now (validation tie, exact SHAP, lower RAM); the transformer is the first candidate to deploy once it has an explainer and repeated-seed evaluation.\n\n**Conclusion.** Frozen embeddings lose to TF-IDF; fine-tuning wins modestly. Transformers are not automatically better on ~2.6k short, noisy claims. Bigger Indic models (IndicBERT v2, MuRIL) on a GPU are the next experiment."),
])

nb("07_model_explainability.ipynb", [
    ("md", "# 07 — Model explainability\n\n**Objective.** Compute SHAP explanations for the deployed linear model and verify our fast implementation against the `shap` library."),
    ("code", SETUP),
    ("code", "import joblib, shap\nfrom ml.explainability.explain import LinearExplainer\nfrom ml.preprocessing.text_cleaning import model_text\nclf = joblib.load(ARTIFACTS_DIR / 'classifier.joblib')\nex = LinearExplainer(clf, background_mean=np.load(ARTIFACTS_DIR / 'explainer_background_mean.npy'))\nout = ex.explain(model_text('Old video from Bangladesh shared as police firing on protesters in Delhi'))\nprint(out['target_class'], out['method']); pd.DataFrame(out['top_features'])"),
    ("md", "## Additivity (SHAP efficiency)\nbase + Σ contributions of present features + absent-feature term = model output."),
    ("code", "full = ex.explain(model_text('Viral video claims the RBI banned ₹500 notes'), top_k=10**6)\nprint(full['base_value'] + sum(f['contribution'] for f in full['top_features']) + full['absent_features_contribution'], '==', full['output_value'])"),
    ("md", "## Agreement with the shap library"),
    ("code", "feats = clf.named_steps['features']; sub = df.dropna(subset=['verdict']).head(100)\nbg = feats.transform(sub.claim_text.map(model_text)); ex2 = LinearExplainer(clf).fit_background(sub.claim_text.map(model_text).tolist())\ntext = model_text('old video of flood shared as recent'); c = list(clf.classes_).index('OUTDATED')\nlib = shap.LinearExplainer((clf.named_steps['clf'].coef_[c], clf.named_steps['clf'].intercept_[c]), bg).shap_values(feats.transform([text]))\nours = {f['feature']: f['contribution'] for f in ex2.explain(text, 'OUTDATED', top_k=8)['top_features']}\nnames = list(ex2.names)\npd.DataFrame({'ours': ours, 'shap library': {k: float(np.ravel(lib)[names.index(k)]) for k in ours}})"),
    ("md", "## Global view: strongest n-grams per class"),
    ("code", "W = clf.named_steps['clf'].coef_\nfor i, cl in enumerate(clf.classes_):\n    top = np.argsort(-W[i])[:12]; print(cl, '→', ', '.join(repr(ex.names[j]) for j in top))"),
    ("md", "## Observations\n* Our sparse implementation matches `shap.LinearExplainer` to ~1e-6.\n* OUTDATED is driven by temporal words (साल 'year', ಇತ್ತೀಚಿನ 'recent', 'recent'); MISLEADING by provenance phrasing ('video from', 'photos show') — plausible model behaviour, **not proof** that these words indicate misinformation.\n* **Bias finding:** the word 'muslim' is among the strongest MISLEADING features. This mirrors which communal claims fact-checkers debunked (often real footage miscaptioned with a communal angle), not anything about the community; it is a reason the classifier must never judge a claim alone, and a candidate for feature masking or counterfactual evaluation.\n\n**Conclusion.** Explanations are faithful to the model and cheap enough to compute on every request."),
])

nb("08_error_analysis.ipynb", [
    ("md", "# 08 — Error analysis\n\n**Objective.** Inspect where the deployed classifier and the retrieval system fail."),
    ("code", SETUP),
    ("code", "pred = pd.read_csv(ARTIFACTS_DIR / 'test_predictions.csv')\npred['correct'] = pred.label == pred.predicted\nprint(f\"test accuracy {pred.correct.mean():.3f}\"); pd.crosstab(pred.label, pred.predicted, normalize='index').round(2)"),
    ("md", "## Most confident mistakes"),
    ("code", "pred[~pred.correct].sort_values('confidence', ascending=False).head(12)[['label','predicted','confidence','language','claim_text']]"),
    ("md", "## Errors by language and input type"),
    ("code", "pred.groupby(['language','claim_source'])['correct'].agg(['mean','size']).round(3)"),
    ("md", "## Accuracy against confidence"),
    ("code", "pred['bucket'] = pd.cut(pred.confidence, [0, .4, .5, .6, .7, .8, 1])\npred.groupby('bucket', observed=True)['correct'].agg(['mean','size']).round(3)"),
    ("md", "## Retrieval evaluation"),
    ("code", "rev = json.loads((ARTIFACTS_DIR / 'retrieval_eval.json').read_text())\npd.DataFrame({k: {m: rev[k][m] for m in ('recall@1','recall@5','recall@10','mrr')} for k in ('hybrid','tfidf_char')}).T"),
    ("code", "pt = pd.DataFrame(rev['hybrid']['precision_at_threshold']).T\nax = pt.plot(marker='o'); ax.set_xlabel('score threshold'); ax.set_title('Hybrid retrieval: top-1 precision vs coverage'); plt.show(); pt"),
    ("md", "## Observations\n* The largest confusion is FALSE ↔ MISLEADING (26–30% of each class), and a third of OUTDATED claims are predicted FALSE: an old video shared out of context fits several labels, and the rule-based labels add noise.\n* Confidence is informative: accuracy is ~76% above 0.8 confidence versus ~44% below 0.6.\n* Retrieval at score ≥ 0.60 is right ~95% of the time when the claim is in the dataset; for claims that are *not* in the dataset, false strong matches remain possible, which is why the UI asks users to confirm it is the same claim.\n\n**Conclusion.** The biggest gains would come from (1) human-verified verdict labels, (2) more Hindi claim texts, (3) Indic-specific embeddings."),
])

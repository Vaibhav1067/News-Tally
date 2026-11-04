# Data sources

Access was checked on **2026-11-04** with an honest bot User-Agent
(`NewsTallyResearchBot/0.1; non-commercial student research project`). Re-check before re-collecting.

| Source | Endpoint used | robots.txt | Status | Records collected |
|---|---|---|---|---|
| Factly (English) | `https://factly.in/wp-json/wp/v2/posts?categories=358` | allows `/wp-json` | collected | 1,500 (30 pages × 50) |
| Factly (Kannada) | `https://factly.in/wp-json/wp/v2/posts?categories=376` | allows | collected | 1,072 (whole category) |
| Alt News (English) | `https://www.altnews.in/wp-json/wp/v2/posts` | allows | collected | 735 kept of 1,250 posts (515 had no parseable verdict: reporting, not fact-checks) |
| Alt News (Hindi) | `https://www.altnews.in/hindi/wp-json/wp/v2/posts` | allows | collected | 831 kept of 1,250 posts (419 dropped) |
| BOOM Live | robots.txt and RSS | **HTTP 403** | **not collected** — refusal respected | 0 |
| PIB Fact Check | `factcheck.pib.gov.in` | **HTTP 401 / "inaccessible"** | **not collected**; its main channel (X) is login-gated | 0 |

After cleaning and de-duplication: **4,137 records** (1 exact duplicate claim removed), published
2019-10-24 to 2026-11-03. Exact counts are recomputed on every build in
`data/metadata/dataset_report.json`; run logs are in `data/metadata/collection_log.jsonl`.

## What is stored per record

| Field | Source |
|---|---|
| `claim_id` | SHA-1 of publisher + URL (stable across runs) |
| `claim_text` | Factly's "Claim:" block when present (`claim_source=claim_field`), otherwise the headline (`claim_source=title`) |
| `fact_check_title`, `fact_check_url`, `publication_date` | API fields |
| `verdict`, `verdict_raw`, `verdict_rule` | normalised by `ml/data_collection/verdict_normalizer.py`; `None` if no rule matched |
| `explanation` | **one** conclusion sentence ("To sum up, …"), ≤ 300 characters |
| `category`, `category_source` | first topical publisher tag, else keyword inference (marked as such) |
| `language`, `publisher`, `collection_date` | source config / run time |

Full article bodies are **not** stored. Every record links to the original article, which remains
the authoritative source. The project is non-commercial research; if a publisher objects, delete
their records with `data/raw/<source>_*.jsonl` removal and a rebuild.

## Verdict normalisation

Publishers write verdicts in prose. Ordered rules map them to the shared schema:

| Priority | Rule family | Examples | Verdict |
|---|---|---|---|
| 0 | explicit non-manipulation | "the video is NOT a deepfake" | TRUE |
| 1 | manipulated media | deepfake, AI-generated, morphed, एडिटेड, ಎಡಿಟ್ | FALSE |
| 2 | old content | old video, predates, पुराना, ಹಳೆಯ, "2017ರ ವಿಡಿಯೋ" | OUTDATED |
| 3 | missing context | unrelated, falsely shared as, scripted, भ्रामक, ಅಸಂಬಂಧಿತ | MISLEADING |
| 4 | generic falsity | fake, false, did not say, फ़र्ज़ी, ಸುಳ್ಳು | FALSE |
| 5–6 | no evidence / unverifiable | no evidence, could not be verified | INSUFFICIENT_EVIDENCE / UNVERIFIED |
| 7 | explicit confirmation | "the claim is true" (negation-checked) | TRUE |

Result: FALSE 1,530 · MISLEADING 1,350 · OUTDATED 749 · TRUE 6 · INSUFFICIENT_EVIDENCE 4 ·
UNVERIFIED 1 · **unparsed 497**. Audit results and known error modes: `data/metadata/verdict_audit.md`.

## Importing other datasets

Datasets you download yourself (after accepting their licence) go in `data/external/`:

```bash
python -m ml.data_collection.importer data/external/my_dataset.csv \
  --publisher "Dataset name (licence)" --map claim_text=text verdict_raw=label fact_check_url=url
```

Explicit labels such as "false", "half true", "unproven" are mapped; anything else goes through the
same verdict rules and stays `None` if unmatched.

## Photographs used on the website

All via Wikimedia Commons, credited in the site footer (`docs/image_credits.json`):

* "Street Newspaper Reading - Manicktala - Kolkata 2014-02-23" by Biswarup Ganguly, CC BY 3.0 — https://commons.wikimedia.org/w/index.php?curid=31360367
* "Safe Newspaper Vendor - coronavirus" by Vaikunda Raja, CC BY-SA 4.0 — https://commons.wikimedia.org/w/index.php?curid=88731857
* "Assam tribune picture" by Vikramjit Kakati, CC BY-SA 4.0 — https://commons.wikimedia.org/w/index.php?curid=37047186

The images were resized for the web (an adaptation; the CC BY-SA licence applies to the resized files).

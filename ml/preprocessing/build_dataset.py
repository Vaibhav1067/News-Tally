"""Build the processed dataset from every raw JSONL file.

    python -m ml.preprocessing.build_dataset

Steps: load raw -> validate -> clean -> exact dedup -> language check ->
near-duplicate grouping -> length features -> save CSV/JSONL -> write a data
quality report (data/metadata/dataset_report.json) that the EDA dashboard and
notebooks read. Every number in that report is computed here from real rows.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import pandas as pd

from ml.config import METADATA_DIR, PROCESSED_DATASET, PROCESSED_DATASET_JSON, RAW_DIR
from ml.data_collection.verdict_normalizer import normalize_verdict
from ml.preprocessing.dedup import drop_exact_duplicates, near_duplicate_groups
from ml.preprocessing.language import detect_language
from ml.preprocessing.text_cleaning import clean_text
from ml.preprocessing.validation import validate_frame

log = logging.getLogger("build_dataset")

TEXT_COLS = ["claim_text", "fact_check_title", "explanation", "category"]

# Harmonise publisher tags across editions (Hindi tag names -> shared English names)
CATEGORY_MAP = {
    "राजनीति": "Politics", "धर्म": "Religion & Communal", "Religion": "Religion & Communal",
    "मीडिया एनेलिसिस": "Media analysis", "समाचार": "News", "अंतरराष्ट्रीय पॉलिटिक्स": "International politics",
    "Coronavirus Kannada": "Health", "Coronavirus English": "Health", "Coronavirus": "Health", "COVID19": "Health",
    "विज्ञान": "Science", "समाज": "Society", "इतिहास": "History", "finance": "Finance",
}


def load_raw() -> pd.DataFrame:
    frames = []
    for path in sorted(RAW_DIR.glob("*.jsonl")):
        df = pd.read_json(path, lines=True, dtype=False)
        df["raw_file"] = path.name
        frames.append(df)
    if not frames:
        raise SystemExit(f"No raw files in {RAW_DIR}. Run ml.data_collection.run_collection first.")
    return pd.concat(frames, ignore_index=True)


def build() -> dict:
    raw = load_raw()
    report: dict = {"built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "raw_rows": int(len(raw)), "raw_files": sorted(raw["raw_file"].unique().tolist())}

    # missing-value profile BEFORE cleaning (what the sources actually gave us)
    report["missing_pct_raw"] = {c: round(float(raw[c].isna().mean() * 100), 2)
                                 for c in raw.columns if c != "raw_file"}

    for c in TEXT_COLS:
        raw[c] = raw[c].map(lambda v: clean_text(v) if isinstance(v, str) else v)
        raw[c] = raw[c].replace("", None)

    # Re-apply the CURRENT verdict rules (so rule fixes don't require re-crawling).
    # Imported datasets with explicit labels keep their label.
    before = raw["verdict"].copy()
    renorm = raw["verdict_rule"] != "explicit_label"
    results = [normalize_verdict(t, e) for t, e in zip(raw.loc[renorm, "fact_check_title"],
                                                         raw.loc[renorm, "explanation"])]
    raw.loc[renorm, "verdict"] = [v.value if v else None for v, _, _ in results]
    raw.loc[renorm, "verdict_rule"] = [r for _, r, _ in results]
    raw.loc[renorm, "verdict_raw"] = [m for _, _, m in results]
    report["verdicts_changed_by_renormalisation"] = int((before.fillna("-") != raw["verdict"].fillna("-")).sum())

    raw["category"] = raw["category"].map(lambda c: CATEGORY_MAP.get(c, c) if isinstance(c, str) else c)

    valid, invalid = validate_frame(raw)
    report["invalid_rows"] = int(len(invalid))
    if len(invalid):
        invalid.to_csv(METADATA_DIR / "invalid_rows.csv", index=False)

    deduped, dup_stats = drop_exact_duplicates(valid)
    report.update(dup_stats)

    # Re-detect language from the text itself and flag disagreements with the source label.
    detected = deduped["claim_text"].map(lambda t: detect_language(t).code)
    deduped["detected_language"] = detected
    report["language_label_disagreement"] = int((detected != deduped["language"]).sum())

    deduped["group_id"] = near_duplicate_groups(deduped["claim_text"].tolist(), threshold=0.8)
    group_sizes = deduped["group_id"].map(deduped["group_id"].value_counts())
    report["near_duplicate_rows"] = int((group_sizes > 1).sum())
    report["near_duplicate_groups"] = int((deduped["group_id"].value_counts() > 1).sum())

    deduped["claim_length_chars"] = deduped["claim_text"].str.len()
    deduped["claim_length_words"] = deduped["claim_text"].str.split().str.len()
    deduped = deduped.drop(columns=["raw_file"]).sort_values("publication_date", ascending=False)

    deduped.to_csv(PROCESSED_DATASET, index=False, encoding="utf-8")
    deduped.to_json(PROCESSED_DATASET_JSON, orient="records", lines=True, force_ascii=False)

    n = len(deduped)
    report.update({
        "final_rows": int(n),
        "duplicate_pct": round(100 * (report["raw_rows"] - report["invalid_rows"] - n) / max(report["raw_rows"], 1), 2),
        "verdict_distribution": deduped["verdict"].fillna("UNPARSED").value_counts().to_dict(),
        "language_distribution": deduped["language"].value_counts().to_dict(),
        "publisher_distribution": deduped["publisher"].value_counts().to_dict(),
        "claim_source_distribution": deduped["claim_source"].value_counts().to_dict(),
        "category_source_distribution": deduped["category_source"].fillna("none").value_counts().to_dict(),
        "top_categories": deduped["category"].fillna("Uncategorised").value_counts().head(15).to_dict(),
        "date_range": [str(deduped["publication_date"].min()), str(deduped["publication_date"].max())],
        "claim_length_words": deduped["claim_length_words"].describe().round(1).to_dict(),
        "missing_pct_processed": {c: round(float(deduped[c].isna().mean() * 100), 2) for c in deduped.columns},
    })
    (METADATA_DIR / "dataset_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                                      encoding="utf-8")
    return report


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    report = build()
    log.info("Processed %d rows (from %d raw). Verdicts: %s", report["final_rows"], report["raw_rows"],
             report["verdict_distribution"])
    log.info("Saved %s and dataset_report.json", PROCESSED_DATASET)


if __name__ == "__main__":
    main()
